import json
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from signals import analyze_signal  # Функция анализа из signals.py

session = HTTP(testnet=False)

def load_tickers():
    with open('tickers.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_klines(symbol, interval='15', limit=200):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Ошибка API: {res.get('retMsg', 'Неизвестная ошибка')}")

    kline_list = res['result']['list']
    df = pd.DataFrame(kline_list, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    oi_df = get_open_interest(symbol, interval)
    df = pd.merge(df, oi_df, on='open_time', how='left')
    return df

def get_open_interest(symbol, interval='15'):
    interval_map = {
        '15': '15m', '30': '30m', '60': '1h',
        '240': '4h', 'D': '1d'
    }
    if interval not in interval_map:
        raise ValueError(f"Неизвестный интервал: {interval}")

    now_ts = int(datetime.utcnow().timestamp() * 1000)

    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        interval=interval_map[interval],
        intervalTime=now_ts
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Ошибка OI: {res.get('retMsg', 'Неизвестная ошибка')}")

    oi_list = res['result']['list']
    df = pd.DataFrame(oi_list)
    df['open_time'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time', 'open_interest']]

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
    df['isBuyerMaker'] = df['side'] == 'Sell'  # продавец = маркет-мейкер
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

    all_klines = get_klines(symbol, interval='15', limit=2000)
    all_klines = all_klines[(all_klines['open_time'] >= start) & (all_klines['open_time'] < now)].reset_index(drop=True)

    long_entries = 0
    short_entries = 0

    for idx in range(50, len(all_klines)):  # Пропустим первые 50, чтобы индикаторы стабилизировались
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
