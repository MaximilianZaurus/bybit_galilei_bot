# signals.py
import httpx
import pandas as pd
from ta.trend import ADXIndicator
from ta.volatility import BollingerBands
from ta.momentum import CMOIndicator
from ta.trend import PSARIndicator

BYBIT_URL = "https://api.bybit.com/v5/market/kline"
TICKERS = [
    "BTCUSDT", "ETHUSDT", "AAVEUSDT", "SOLUSDT", "XMRUSDT",
    "TONUSDT", "NEARUSDT", "LTCUSDT", "APTUSDT", "WLDUSDT"
]

async def get_ohlcv(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    async with httpx.AsyncClient() as client:
        params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit}
        r = await client.get(BYBIT_URL, params=params)
        data = r.json()
        df = pd.DataFrame(data["result"]["list"], columns=[
            "timestamp", "open", "high", "low", "close", "volume", "turnover"
        ])
        df = df.iloc[::-1]
        df["close"] = pd.to_numeric(df["close"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["open"] = pd.to_numeric(df["open"])
        return df.reset_index(drop=True)

async def check_galilei_signal(symbol: str) -> bool:
    df_1h = await get_ohlcv(symbol, "60")
    df_30m = await get_ohlcv(symbol, "30")
    df_5m = await get_ohlcv(symbol, "5")

    # Условие 1: Bollinger lower band touch (1h)
    bb = BollingerBands(close=df_1h["close"], window=20, window_dev=2)
    if df_1h["close"].iloc[-1] > bb.bollinger_lband().iloc[-1]:
        return False

    # Условие 2: CMO < -55 (30m)
    cmo = CMOIndicator(close=df_30m["close"], window=14)
    if cmo.cmo().iloc[-1] > -55:
        return False

    # Условие 3: ADX > 35 (30m)
    adx = ADXIndicator(high=df_30m["high"], low=df_30m["low"], close=df_30m["close"], window=14)
    if adx.adx().iloc[-1] < 35:
        return False

    # Условие 4: Parabolic SAR разворот вверх (5m)
    psar = PSARIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"])
    last_psar = psar.psar().iloc[-1]
    if last_psar > df_5m["close"].iloc[-1]:
        return False

    return True
