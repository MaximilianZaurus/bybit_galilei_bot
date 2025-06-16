import asyncio
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from signals import analyze_signal
from json import load as json_load

session = HTTP(testnet=False)

# Загрузка тикеров из файла tickers.json
def load_tickers(filename="tickers.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json_load(f)

# Получение свечей
def get_klines(symbol, interval='15', total_limit=2000):
    max_limit = 1000
    interval_map = {
        '1': 60, '3': 180, '5': 300, '15': 900,
        '30': 1800, '60': 3600, '120': 7200,
        '240': 14400, 'D': 86400
    }
    if interval not in interval_map:
        raise ValueError(f"Unsupported interval: {interval}")

    result = []
    end_time = int(datetime.utcnow().timestamp())
    count = 0

    while count < total_limit:
        limit = min(max_limit, total_limit - count)
        res = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit,
            end=end_time * 1000
        )
        if res.get('retCode', 1) != 0:
            raise Exception(f"API get_kline error: {res.get('retMsg')}")

        klines = res['result']['list']
        if not klines:
            break

        result = klines + result
        count += len(klines)
        oldest_time = int(klines[-1][0]) // 1000
        end_time = oldest_time - interval_map[interval]

    # Проверка: достаточное количество колонок
    if len(result[0]) < 8:
        raise Exception("Недостаточно данных в свечах. Проверь возвращаемые поля API.")

    df = pd.DataFrame(result, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest'
    ])

    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
        df[col] = df[col].astype(float)

    return df.sort_values('open_time').reset_index(drop=True)

# Получение последних трейдов
def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.query_recent_trading_records(symbol=symbol, limit=limit)
    if res.get('retCode', 1) != 0:
        raise Exception(f"API trades error: {res.get('retMsg')}")
    trades_df = pd.DataFrame(res['result'])
    trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time'], unit='ms')
    trades_df = trades_df[(trades_df['trade_time'] >= start_time) & (trades_df['trade_time'] < end_time)]
    for col in ['price', 'qty']:
        trades_df[col] = trades_df[col].astype(float)
    trades_df['isBuyerMaker'] = trades_df['isBuyerMaker'].astype(bool)
    return trades_df

# CVD
def calculate_cvd(trades_df):
    buy_volume = trades_df[trades_df['isBuyerMaker'] == False]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker'] == True]['qty'].sum()
    return buy_volume - sell_volume

# ΔOI
def calculate_oi_delta(df, window=3):
    if len(df) < window + 1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window-1]

# ADX
def calculate_adx(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    plus_di = 100 * (plus_dm.rolling(period).sum() / atr)
    minus_di = 100 * (minus_dm.rolling(period).sum() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    return adx.iloc[-1] if not adx.empty else 0.0

# Главная функция анализа
async def analyze_and_send(send_message):
    tickers = load_tickers()
    now = datetime.utcnow()
    start = now - timedelta(days=7)

    for ticker in tickers:
        try:
            df = get_klines(ticker, interval='15', total_limit=2000)
            df = df[(df['open_time'] >= start) & (df['open_time'] < now)].reset_index(drop=True)
            if df.empty:
                continue

            candle_time = df['open_time'].iloc[-1]
            trades = get_trades(ticker, candle_time, candle_time + timedelta(minutes=15))
            cvd = calculate_cvd(trades)
            oi_delta = calculate_oi_delta(df)
            adx = calculate_adx(df)

            signals = analyze_signal(df, cvd=cvd, oi_delta=oi_delta, adx=adx)

            msg = (
                f"📊 <b>{ticker}</b>\n"
                f"Цена: {df['close'].iloc[-1]:.4f} | RSI: {signals.get('rsi', 0):.1f} | "
                f"MACD: {signals.get('macd_hist', 0):.3f} | ADX: {adx:.1f}\n"
                f"CVD: {cvd:.1f} | ΔOI: {oi_delta:.1f}\n"
                f"🟢 Лонг: {'✅' if signals.get('long_entry') else '—'}\n"
                f"🔴 Шорт: {'✅' if signals.get('short_entry') else '—'}"
            )

            await send_message(msg)

        except Exception as e:
            await send_message(f"⚠️ Ошибка при анализе {ticker}: {e}")

# Тестовая отправка
if __name__ == "__main__":
    async def dummy_send(msg):
        print(msg)

    asyncio.run(analyze_and_send(dummy_send))
