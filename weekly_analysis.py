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

def get_klines(symbol, interval="15", limit=672):
    res = session.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
    if res.get("retCode", 1) != 0:
        raise Exception(f"Kline error for {symbol}: {res.get('retMsg')}")
    df = pd.DataFrame(res["result"]["list"], columns=["open_time","open","high","low","close","volume","turnover"])
    df["open_time"] = pd.to_datetime(df["open_time"].astype(float),unit="ms")
    for c in ["open","high","low","close","volume","turnover"]:
        df[c] = df[c].astype(float)
    return df

def get_open_interest(symbol, interval="15", limit=672):
    res = session.get_open_interest(category="linear", symbol=symbol, interval=interval, limit=limit)
    if res.get("retCode",1)!=0:
        raise Exception(f"OI error for {symbol}: {res.get('retMsg')}")
    raw = res["result"]["list"]
    df = pd.DataFrame(raw)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float),unit="ms")
    df["openInterest"] = df["openInterest"].astype(float)
    return df

def get_trades(symbol, limit=1000):
    res = session.get_public_trading_records(category="linear", symbol=symbol, limit=limit)
    if res.get("retCode",1)!=0:
        raise Exception(f"Trades error for {symbol}: {res.get('retMsg')}")
    df = pd.DataFrame(res["result"]["list"])
    df["size"] = df["qty"].astype(float)
    df["cvd"] = df.apply(lambda r: r["size"] if r["side"]=="Buy" else -r["size"],axis=1).cumsum()
    return df

def analyze_week():
    tickers = load_tickers()
    msgs = []
    for sym in tickers:
        try:
            kl = get_klines(sym)
            if len(kl)<20: raise Exception("мало свечей")
            close = kl["close"]
            rsi = ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]
            macd = ta.trend.MACD(close).macd_diff()
            if len(macd)<2: raise Exception("мало MACD")
            mh, mprev = macd.iloc[-1], macd.iloc[-2]
            trend = "↑" if mh>mprev else "↓"

            oi = get_open_interest(sym)
            if len(oi)<2: raise Exception("мало данных по OI")
            oi_d = oi["openInterest"].iloc[-1] - oi["openInterest"].iloc[-2]

            tr = get_trades(sym)
            if len(tr)<2: raise Exception("мало трейдов")
            cvd_d = tr["cvd"].iloc[-1] - tr["cvd"].iloc[-2]

            msgs.append(f"{sym}: RSI {rsi:.1f}, MACD {mh:.3f} {trend}, ΔOI {oi_d:.1f}, ΔCVD {cvd_d:.1f}")
        except Exception as e:
            logger.error(f"{sym}: {e}")
            msgs.append(f"{sym}: ❌ {e}")
    return "Weekly Overview:\n" + "\n".join(msgs)

if __name__=="__main__":
    print(analyze_week())
