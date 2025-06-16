import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from pybit.unified_trading import HTTP
from signals import analyze_signal  # твоя функция анализа из signals.py

session = HTTP(endpoint="https://api.bybit.com")

def load_tickers(filepath='tickers.json'):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Файл {filepath} не найден")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def get_klines(symbol, interval='15', limit=200, start_time=None, end_time=None):
    """
    Получает свечи с Bybit v5.
    interval — строка, например '15' (минуты).
    """
    res = session.query_kline(symbol=symbol, interval=interval, limit=limit)
    if res['ret_code'] != 0:
        raise Exception(f"Ошибка API get_klines: {res['ret_msg']}")
    df = pd.DataFrame(res['result'])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
        df[col] = df[col].astype(float)
    if start_time and end_time:
        df = df[(df['open_time'] >= start_time) & (df['open_time'] < end_time)]
    return df.reset_index(drop=True)

def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.query_recent_trading_records(symbol=symbol, limit=limit)
    if res['ret_code'] != 0:
        raise Exception(f"Ошибка API trades: {res['ret_msg']}")
    trades_df = pd.DataFrame(res['result'])
    trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time'], unit='ms')
    trades_df = trades_df[(trades_df['trade_time'] >= start_time) & (trades_df['trade_time'] < end_time)]
    for col in ['price', 'qty']:
        trades_df[col] = trades_df[col].astype(float)
    trades_df['isBuyerMaker'] = trades_df['isBuyerMaker'].astype(bool)
    return trades_df.reset_index(drop=True)

def calculate_cvd(trades_df):
    buy_volume = trades_df[trades_df['isBuyerMaker'] == False]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker'] == True]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    if len(df) < window + 1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window-1]

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
        if signals.get('long_entry'):
            long_entries += 1
        if signals.get('short_entry'):
            short_entries += 1

    print(f"{symbol} за последнюю неделю:")
    print(f"  Входы в Лонг: {long_entries}")
    print(f"  Входы в Шорт: {short_entries}")

if __name__ == "__main__":
    tickers = load_tickers()
    for symbol in tickers:
        try:
            analyze_week(symbol)
        except Exception as e:
            print(f"Ошибка при анализе {symbol}: {e}")
