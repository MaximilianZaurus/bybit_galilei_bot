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

async def check_galilei_signal(symbol: str) -> tuple[bool, dict]:
    df_1h = await get_ohlcv(symbol, "60")
    df_30m = await get_ohlcv(symbol, "30")
    df_5m = await get_ohlcv(symbol, "5")

    bb = BollingerBands(close=df_1h["close"], window=20, window_dev=2)
    lower_band = bb.bollinger_lband().iloc[-1]
    close_1h = df_1h["close"].iloc[-1]
    condition1 = close_1h <= lower_band

    cmo = CMOIndicator(close=df_30m["close"], window=14)
    cmo_val = cmo.cmo().iloc[-1]
    condition2 = cmo_val < -55

    adx = ADXIndicator(high=df_30m["high"], low=df_30m["low"], close=df_30m["close"], window=14)
    adx_val = adx.adx().iloc[-1]
    condition3 = adx_val > 35

    psar = PSARIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"])
    psar_val = psar.psar().iloc[-1]
    close_psar = df_5m["close"].iloc[-1]
    condition4 = psar_val < close_psar

    all_conditions = condition1 and condition2 and condition3 and condition4

    return all_conditions, {
        "cmo": cmo_val,
        "adx": adx_val,
        "psar": psar_val,
        "close_psar": close_psar
    }
