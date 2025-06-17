import pandas as pd
from ta.volume import ChaikinMoneyFlowIndicator
from pybit.unified_trading import HTTP

client = HTTP(testnet=False)

def analyze_ticker(ticker: str, interval: str = "15"):
    candles = client.get_kline(category="linear", symbol=ticker, interval=interval, limit=3)["result"]["list"]
    df = pd.DataFrame(candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume", "turnover"
    ])
    df = df.iloc[::-1]
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)

    close_now = df.iloc[-1]["close"]
    close_prev = df.iloc[-2]["close"]
    price_change = ((close_now - close_prev) / close_prev) * 100

    oi_data = client.get_open_interest(category="linear", symbol=ticker, interval=interval, limit=3)["result"]["list"]
    oi_now = float(oi_data[-1]["openInterest"])
    oi_prev = float(oi_data[-2]["openInterest"])
    oi_delta = "растет" if oi_now > oi_prev else "падает"

    cvd = df["volume"].diff().fillna(0)
    cvd_trend = "растет" if cvd.iloc[-1] > 0 else "падает"

    signal = ""
    if price_change > 0 and oi_now > oi_prev and cvd_trend == "растет":
        signal = "Сильный лонг"
    elif price_change < 0 and oi_now > oi_prev and cvd_trend == "падает":
        signal = "Сильный лонг"

    return f"{ticker} | Закр: {close_now:.2f} ({price_change:+.2f}%) | OI: {oi_delta} | CVD: {cvd_trend} | {signal}"
