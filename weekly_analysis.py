from pybit.unified_trading import HTTP
import pandas as pd
import ta
import json
from datetime import datetime, timedelta

# ✅ Загрузка тикеров
def get_tickers():
    with open("tickers.json", "r") as f:
        return json.load(f)

# ✅ Сессия Bybit
session = HTTP(testnet=False)

# ✅ Получение свечей (v5)
def get_klines(symbol, interval='1h', limit=168):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Kline API error: {res['retMsg']}")

    kline_list = res['result']['list']
    if not kline_list:
        raise Exception("Kline data is empty")

    # Обработка: список списков или список словарей
    if isinstance(kline_list[0], list):
        df = pd.DataFrame(kline_list, columns=[
            'start', 'open', 'high', 'low', 'close', 'volume', 'turnover'
        ])
        df['start'] = df['start'].astype(int)
    else:
        df = pd.DataFrame(kline_list)
        df['start'] = df['start'].astype(int)

    df['open_time'] = pd.to_datetime(df['start'], unit='s')

    # Приведение к float
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        df[col] = df[col].astype(float)
    df['turnover'] = df.get('turnover', 0.0).astype(float)

    return df[['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover']]

# ✅ Получение OI (v5)
def get_open_interest(symbol, interval='1h'):
    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        intervalTime=interval
    )
    if res['retCode'] != 0:
        raise Exception(f"OI API error: {res['retMsg']}")

    if not res['result']['list']:
        raise Exception("Open Interest data is empty")

    df = pd.DataFrame(res['result']['list'])

    if 'timestamp' not in df or 'openInterest' not in df:
        raise Exception("Invalid OI response format")

    df['open_time'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time', 'open_interest']]

# ✅ Получение трейдов (v5)
def get_trades(symbol, start_time, end_time):
    res = session.get_trade_history(
        category="linear",
        symbol=symbol,
        limit=1000
    )
    if res['retCode'] != 0:
        raise Exception(f"Trade API error: {res['retMsg']}")

    if not res['result']['list']:
        raise Exception("Trade history is empty")

    df = pd.DataFrame(res['result']['list'])

    if 'execTime' not in df or 'execQty' not in df or 'side' not in df:
        raise Exception("Invalid trade history format")

    df['trade_time'] = pd.to_datetime(df['execTime'].astype(int), unit='ms')
    df = df[(df['trade_time'] >= start_time) & (df['trade_time'] < end_time)]
    df['qty'] = df['execQty'].astype(float)
    df['isBuyerMaker'] = df['side'] == 'Sell'
    return df

# ✅ CVD
def calculate_cvd(trades_df):
    buy_volume = trades_df[~trades_df['isBuyerMaker']]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker']]['qty'].sum()
    return buy_volume - sell_volume

# ✅ ΔOI
def calculate_oi_delta(df, window=3):
    if len(df) < window + 1 or 'open_interest' not in df.columns:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window - 1]

# ✅ Анализ по одному символу
def analyze_single_symbol(symbol: str) -> str:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # Получение свечей
    df = get_klines(symbol, interval='1h', limit=168)
    if df.empty or len(df) < 20:
        raise Exception("Недостаточно данных по свечам")

    # Получение OI
    oi_df = get_open_interest(symbol, interval='1h')
    if oi_df.empty:
        raise Exception("Недостаточно данных по Open Interest")

    df = pd.merge(df, oi_df, on='open_time', how='left')
    df['open_interest'] = df['open_interest'].fillna(method='ffill')

    # Получение трейдов
    trades_df = get_trades(symbol, week_ago, now)
    if trades_df.empty:
        raise Exception("Нет трейдов за последние 7 дней")

    # Расчёты
    cvd = calculate_cvd(trades_df)
    oi_delta = calculate_oi_delta(df)

    close = df['close'].dropna()
    if close.empty or len(close) < 20:
        raise Exception("Недостаточно цен закрытия для TA")

    try:
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi().dropna().iloc[-1]
        macd_hist = ta.trend.MACD(close).macd_diff().dropna().iloc[-1]
    except Exception as e:
        raise Exception(f"Ошибка расчета индикаторов: {e}")

    macd_dir = "↑" if macd_hist > 0 else "↓"
    trend = "⏫ Uptrend" if macd_hist > 0 else "⏬ Downtrend"

    return f"{symbol}: RSI {rsi:.1f}, MACD {macd_hist:.3f} {macd_dir}, ΔOI {oi_delta:.1f}, CVD {cvd:.1f} {trend}"

# ✅ Основной анализ
def analyze_week() -> str:
    tickers = get_tickers()
    result_lines = ["📊 Weekly Overview:"]
    for symbol in tickers:
        try:
            line = analyze_single_symbol(symbol)
            result_lines.append(line)
        except Exception as e:
            result_lines.append(f"{symbol}: ❌ Ошибка анализа: {e}")
    return "\n".join(result_lines)

# ✅ Точка входа
if __name__ == "__main__":
    print(analyze_week())
