import json
import pandas as pd
from datetime import datetime
from pybit.unified_trading import HTTP
import ta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session = HTTP(testnet=False)

INTERVAL_MAP = {
    '1': '1m',
    '3': '3m',
    '5': '5m',
    '15': '15m',
    '30': '30m',
    '60': '1h',
    '120': '2h',
    '240': '4h',
    '360': '6h',
    '720': '12h',
    'D': '1d'
}

def load_tickers(path="tickers.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_klines(symbol, interval='15', limit=672):  # 15 мин * 672 = 7 дней
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Kline error for {symbol}: {res['retMsg']}")

    raw_list = res['result']['list']
    if len(raw_list) < 20:
        raise ValueError("Недостаточно данных от Kline")

    df = pd.DataFrame(raw_list, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    return df

def get_open_interest(symbol, interval='15', limit=672):
    interval_str = INTERVAL_MAP.get(str(interval))
    if not interval_str:
        raise ValueError(f"Неподдерживаемый интервал для OI: {interval}")

    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        intervalTime=interval_str,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"OI error for {symbol}: {res['retMsg']}")

    raw = res['result']['list']
    if len(raw) < 2:
        raise ValueError("Недостаточно данных для Open Interest")

    df = pd.DataFrame(raw, columns=["timestamp", "oi"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['oi'] = df['oi'].astype(float)
    return df

def get_trades(symbol, limit=1000):
    res = session.get_public_trading_history(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Trades error for {symbol}: {res['retMsg']}")

    trades = res['result']['list']
    if len(trades) < 2:
        raise ValueError("Недостаточно трейдов для CVD")

    df = pd.DataFrame(trades)
    df['price'] = df['price'].astype(float)
    df['size'] = df['size'].astype(float)
    df['side'] = df['side'].astype(str)
    df['cvd'] = df.apply(lambda row: row['size'] if row['side'] == 'Buy' else -row['size'], axis=1).cumsum()
    return df

def analyze_week():
    tickers = load_tickers()
    messages = []

    for symbol in tickers:
        try:
            df = get_klines(symbol, interval='15', limit=672)
            close = df['close']

            if len(close) < 20:
                raise ValueError("Недостаточно данных для RSI/MACD")

            rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
            macd = ta.trend.MACD(close)
            macd_hist_series = macd.macd_diff()

            if len(macd_hist_series) < 2:
                raise ValueError("Недостаточно данных для MACD histogram")

            macd_hist = macd_hist_series.iloc[-1]
            macd_hist_prev = macd_hist_series.iloc[-2]
            trend = '⏫ Uptrend' if macd_hist > macd_hist_prev else '⏬ Downtrend'

            oi_df = get_open_interest(symbol, interval='15', limit=672)
            oi_change = oi_df['oi'].iloc[-1] - oi_df['oi'].iloc[-2]

            trades_df = get_trades(symbol, limit=1000)
            cvd_change = trades_df['cvd'].iloc[-1] - trades_df['cvd'].iloc[-2]

            msg = (
                f"<b>{symbol} - Weekly Overview</b>\n"
                f"RSI: {rsi:.1f} | MACD hist: {macd_hist:.3f}\n"
                f"{trend}\n"
                f"OI Δ: {oi_change:.2f} | CVD Δ: {cvd_change:.2f}"
            )
            messages.append(msg)

        except Exception as e:
            logger.error(f"Ошибка в анализе {symbol}: {e}")
            messages.append(f"❌ Ошибка анализа {symbol}: {e}")

    final_msg = "📈 <b>Недельный анализ</b>\n\n" + "\n\n".join(messages)
    return final_msg
