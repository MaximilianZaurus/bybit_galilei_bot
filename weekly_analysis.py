import json
from datetime import datetime, timedelta
import pandas as pd
import ta
from pybit.unified_trading import HTTP

# Инициализация сессии Bybit v5 (реальный рынок)
session = HTTP(testnet=False)  # testnet=True для тестовой сети

def load_tickers(path="tickers.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_klines(symbol, interval='15', limit=200):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API get_klines: {res['retMsg']}")
    df = pd.DataFrame(res['result']['list'])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df.reset_index(drop=True)

def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.get_public_trading_records(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API trades: {res['retMsg']}")
    trades_df = pd.DataFrame(res['result']['list'])
    trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time'].astype(float), unit='ms')
    trades_df = trades_df[(trades_df['trade_time'] >= start_time) & (trades_df['trade_time'] < end_time)]
    for col in ['price', 'qty']:
        trades_df[col] = trades_df[col].astype(float)
    trades_df['isBuyerMaker'] = trades_df['isBuyerMaker'].astype(bool)
    return trades_df.reset_index(drop=True)

def calculate_cvd(trades_df):
    buy_volume = trades_df[~trades_df['isBuyerMaker']]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker']]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    if len(df) < window + 1 or 'open_interest' not in df.columns:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window - 1]

def analyze_signal(df, cvd=0, oi_delta=0):
    close = df['close']
    high = df['high']
    low = df['low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_hist = ta.trend.MACD(close).macd_diff().iloc[-1]
    adx = ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1]

    # Для сравнения с предыдущим баром
    macd_hist_prev = ta.trend.MACD(close).macd_diff().iloc[-2]

    long_entry = (
        (adx > 20) and
        (rsi < 35) and
        (macd_hist < 0 and macd_hist > macd_hist_prev) and
        (cvd > 0) and
        (oi_delta > 0)
    )
    long_exit = (
        (adx > 20) and
        (rsi > 60 or macd_hist < macd_hist_prev)
    )
    short_entry = (
        (adx > 20) and
        (rsi > 65) and
        (macd_hist > 0 and macd_hist < macd_hist_prev) and
        (cvd < 0) and
        (oi_delta < 0)
    )
    short_exit = (
        (adx > 20) and
        (rsi < 40 or macd_hist > macd_hist_prev)
    )

    return {
        'long_entry': long_entry,
        'long_exit': long_exit,
        'short_entry': short_entry,
        'short_exit': short_exit,
        'details': {
            'rsi': rsi,
            'macd_hist': macd_hist,
            'adx': adx,
            'close': close.iloc[-1],
            'cvd': cvd,
            'oi_delta': oi_delta
        }
    }

def analyze_week(symbol):
    now = datetime.utcnow()
    start = now - timedelta(days=7)
    all_klines = get_klines(symbol, interval='15', limit=2000)
    all_klines = all_klines[(all_klines['open_time'] >= start) & (all_klines['open_time'] < now)].reset_index(drop=True)

    long_entries = 0
    short_entries = 0

    for idx in range(len(all_klines)):
        df_slice = all_klines.iloc[max(0, idx-200):idx+1]
        if df_slice.empty:
            continue

        candle_time = df_slice['open_time'].iloc[-1]
        start_trades = candle_time
        end_trades = candle_time + timedelta(minutes=15)

        trades = get_trades(symbol, start_trades, end_trades)
        cvd = calculate_cvd(trades)
        oi_delta = calculate_oi_delta(df_slice)

        signals = analyze_signal(df_slice, cvd=cvd, oi_delta=oi_delta)

        if signals['long_entry']:
            long_entries += 1
        if signals['short_entry']:
            short_entries += 1

    print(f"{symbol} за последнюю неделю:")
    print(f"  Входы в Лонг: {long_entries}")
    print(f"  Входы в Шорт: {short_entries}")

if __name__ == "__main__":
    tickers = load_tickers("tickers.json")
    for ticker in tickers:
        analyze_week(ticker)
