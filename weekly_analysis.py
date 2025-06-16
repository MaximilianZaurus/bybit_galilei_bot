import json
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import ta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session = HTTP(testnet=False)

def load_tickers(path="tickers.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_klines(symbol, interval='60', limit=200):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Kline error for {symbol}: {res['retMsg']}")
    raw_list = res['result']['list']
    df = pd.DataFrame(raw_list, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'turnover', 'confirm', 'cross_seq', 'timestamp'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    return df

def analyze_week():
    tickers = load_tickers()
    messages = []

    for symbol in tickers:
        try:
            df = get_klines(symbol, interval='60', limit=168)  # 168 часов ≈ неделя
            close = df['close']

            rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
            macd = ta.trend.MACD(close)
            macd_hist = macd.macd_diff().iloc[-1]
            macd_hist_prev = macd.macd_diff().iloc[-2]

            trend = '⏫ Uptrend' if macd_hist > macd_hist_prev else '⏬ Downtrend'

            msg = (
                f"<b>{symbol} - Weekly Overview</b>\n"
                f"RSI: {rsi:.1f} | MACD hist: {macd_hist:.3f}\n"
                f"{trend}"
            )
            messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка в анализе {symbol}: {e}")
            messages.append(f"❌ Ошибка анализа {symbol}: {e}")

    final_msg = "📈 <b>Недельный анализ</b>\n\n" + "\n\n".join(messages)
    return final_msg
