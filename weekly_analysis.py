import json
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from signals import analyze_signal  # ваша функция анализа

session = HTTP(testnet=False)

def load_tickers():
    with open('tickers.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def round_time(dt, delta):
    seconds = (dt - datetime(1970, 1, 1)).total_seconds()
    rounded = seconds - (seconds % delta.total_seconds())
    return datetime(1970, 1, 1) + timedelta(seconds=rounded)

def get_klines(symbol, interval='15m', limit=2000):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Ошибка API get_kline: {res.get('retMsg', 'Неизвестная ошибка')}")

    kline_list = res['result']['list']
    df = pd.DataFrame(kline_list)
    # Колонки должны соответствовать в ответе: open_time, open, high, low, close, volume, turnover
    # Проверим, есть ли open_time — обычно это timestamp в ms
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    # Подгружаем исторические данные open interest (обновим функцию ниже)
    oi_df = get_open_interest_historical(symbol, interval)
    df = pd.merge(df, oi_df, on='open_time', how='left')
    return df

def get_open_interest_historical(symbol, interval='15m', periods=7*24*4):
    """
    Получаем исторические данные Open Interest за последнюю неделю (7 дней * 24 часа * 4 интервала по 15 минут)
    При этом делаем batch-запросы по интервалу времени, а не по отдельным timestamp.
    """

    delta_map = {
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '4h': timedelta(hours=4),
        '1d': timedelta(days=1),
    }

    if interval not in delta_map:
        raise ValueError(f"Неизвестный интервал: {interval}")

    now = datetime.utcnow()
    end_time = round_time(now, delta_map[interval])
    start_time = end_time - delta_map[interval] * periods

    start_ts = int(start_time.timestamp() * 1000)  # в миллисекундах
    end_ts = int(end_time.timestamp() * 1000)

    # Вызов unified_trading get_open_interest batch
    # Обратите внимание на документацию pybit, параметры могут называться startTime и endTime
    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        interval=interval,
        startTime=start_ts,
        endTime=end_ts
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Ошибка API get_open_interest: {res.get('retMsg', 'Неизвестная ошибка')}")

    oi_list = res['result']['list']
    if not oi_list:
        raise Exception(f"Нет данных Open Interest для {symbol} за период {start_time} - {end_time}")

    df = pd.DataFrame(oi_list)
    # timestamp приходит в миллисекундах (или секундах?) — проверить по доке
    # Допустим в ms
    df['open_time'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time', 'open_interest']].sort_values('open_time').reset_index(drop=True)

def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.get_public_trading_records(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Ошибка API trades: {res.get('retMsg', 'Неизвестная ошибка')}")

    trades = res['result']['list']
    df = pd.DataFrame(trades)
    df['trade_time'] = pd.to_datetime(df['execTime'].astype(float), unit='ms')
    df = df[(df['trade_time'] >= start_time) & (df['trade_time'] < end_time)]
    df['price'] = df['price'].astype(float)
    df['qty'] = df['qty'].astype(float)
    df['isBuyerMaker'] = df['side'] == 'Sell'
    return df

def calculate_cvd(trades_df):
    buy_volume = trades_df[~trades_df['isBuyerMaker']]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker']]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    if len(df) < window + 1 or 'open_interest' not in df.columns:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window - 1]

def analyze_week(symbol):
    now = datetime.utcnow()
    start = now - timedelta(days=7)

    all_klines = get_klines(symbol, interval='15m', limit=2000)
    all_klines = all_klines[(all_klines['open_time'] >= start) & (all_klines['open_time'] < now)].reset_index(drop=True)

    long_entries = 0
    short_entries = 0

    for idx in range(50, len(all_klines)):
        df_slice = all_klines.iloc[max(0, idx - 200):idx + 1]
        if df_slice.empty:
            continue

        candle_time = df_slice['open_time'].iloc[-1]
        start_trades = candle_time
        end_trades = candle_time + timedelta(minutes=15)

        trades = get_trades(symbol, start_trades, end_trades)
        cvd = calculate_cvd(trades)
        oi_delta = calculate_oi_delta(df_slice)

        signals = analyze_signal(df_slice, cvd=cvd, oi_delta=oi_delta)

        if signals.get('long_entry'):
            long_entries += 1
        if signals.get('short_entry'):
            short_entries += 1

    print(f"\n📊 {symbol} за последнюю неделю:")
    print(f"  ✅ Входов в Лонг: {long_entries}")
    print(f"  🔻 Входов в Шорт: {short_entries}")

if __name__ == "__main__":
    tickers = load_tickers()
    for ticker in tickers:
        try:
            analyze_week(ticker)
        except Exception as e:
            print(f"❌ Ошибка анализа {ticker}: {e}")
