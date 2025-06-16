from pybit.unified_trading import HTTP
import pandas as pd
import ta
from datetime import datetime, timedelta

# Инициализация сессии Bybit v5 (реальный рынок)
session = HTTP(testnet=False)  # testnet=True если нужна тестовая сеть

def get_klines(symbol, interval='1h', limit=200):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API: {res['retMsg']}")

    kline_list = res['result']['list']
    df = pd.DataFrame(kline_list, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    return df

def get_open_interest(symbol, interval='1h', limit=200):
    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API OI: {res['retMsg']}")

    oi_data = res['result']['list']
    df = pd.DataFrame(oi_data)
    df['open_time'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time', 'open_interest']]

def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.get_public_trading_records(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API trades: {res['retMsg']}")

    trade_list = res['result']['list']
    df = pd.DataFrame(trade_list)
    df['trade_time'] = pd.to_datetime(df['execTime'].astype(float), unit='ms')
    df = df[(df['trade_time'] >= start_time) & (df['trade_time'] < end_time)]
    df['price'] = df['price'].astype(float)
    df['qty'] = df['qty'].astype(float)
    # "side" == "Sell" значит инициатор продажи, значит isBuyerMaker = True
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

def analyze_signal(df: pd.DataFrame, cvd: float = 0, oi_delta: float = 0) -> dict:
    close = df['close']
    high = df['high']
    low = df['low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_hist = ta.trend.MACD(close).macd_diff()
    adx = ta.trend.ADXIndicator(high, low, close, window=14).adx()

    rsi_curr = rsi.iloc[-1]
    macd_hist_curr = macd_hist.iloc[-1]
    adx_curr = adx.iloc[-1]

    cvd_positive = cvd > 0
    cvd_negative = cvd < 0
    oi_rising = oi_delta > 0
    oi_falling = oi_delta < 0

    long_entry = (
        (adx_curr > 20) and
        (rsi_curr < 35) and
        (macd_hist_curr < 0 and macd_hist_curr > macd_hist.iloc[-2]) and
        cvd_positive and
        oi_rising
    )

    long_exit = (
        (adx_curr > 20) and
        (rsi_curr > 60 or macd_hist_curr < macd_hist.iloc[-2])
    )

    short_entry = (
        (adx_curr > 20) and
        (rsi_curr > 65) and
        (macd_hist_curr > 0 and macd_hist_curr < macd_hist.iloc[-2]) and
        cvd_negative and
        oi_falling
    )

    short_exit = (
        (adx_curr > 20) and
        (rsi_curr < 40 or macd_hist_curr > macd_hist.iloc[-2])
    )

    return {
        'long_entry': long_entry,
        'long_exit': long_exit,
        'short_entry': short_entry,
        'short_exit': short_exit,
        'details': {
            'rsi': rsi_curr,
            'macd_hist': macd_hist_curr,
            'adx': adx_curr,
            'close': close.iloc[-1],
            'cvd': cvd,
            'oi_delta': oi_delta
        }
    }

if __name__ == "__main__":
    symbol = "ETHUSDT"
    interval = "1h"  # часовой интервал

    df = get_klines(symbol, interval=interval, limit=200)
    oi_df = get_open_interest(symbol, interval=interval, limit=200)

    df = pd.merge(df, oi_df, on='open_time', how='left')
    df['open_interest'] = df['open_interest'].fillna(method='ffill')

    # Для трейдов берем последние 15 минут после последней часовой свечи
    end_time = df['open_time'].iloc[-1] + timedelta(minutes=15)
    start_time = end_time - timedelta(minutes=15)

    trades_df = get_trades(symbol, start_time, end_time)
    cvd = calculate_cvd(trades_df)
    oi_delta = calculate_oi_delta(df)

    result = analyze_signal(df, cvd=cvd, oi_delta=oi_delta)

    print("🔎 Текущий анализ:")
    for key, value in result['details'].items():
        print(f"  {key}: {value}")
    print(f"📈 Лонг: {'✅' if result['long_entry'] else '❌'} | 📉 Шорт: {'✅' if result['short_entry'] else '❌'}")
