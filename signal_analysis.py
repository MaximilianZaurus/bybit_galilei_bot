import pandas as pd
import asyncio
from signals import analyze_signal
from typing import Optional

TIMEFRAMES = {
    "15m": "15",
    "1h": "60"
}

class BybitClient:
    # предполагается, что __init__, CVD и OI_HISTORY уже реализованы в bybit_client.py
    # или в расширенной версии этого класса

    async def get_klines(self, symbol: str, timeframe: str, limit: int = 10) -> pd.DataFrame:
        tf = TIMEFRAMES.get(timeframe)
        if tf is None:
            raise ValueError(f"Unsupported timeframe {timeframe}")

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self.http.get_kline(
                symbol=symbol,
                interval=tf,
                limit=limit,
                category=self.category
            )
        )
        if not resp or 'result' not in resp or not resp['result']:
            raise ValueError(f"Empty kline response for {symbol}")

        data = resp['result']
        df = pd.DataFrame(data)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df = df.sort_values('start').reset_index(drop=True)
        return df

    async def analyze_symbol(self, symbol: str, timeframe: str = "15m") -> dict:
        df = await self.get_klines(symbol, timeframe, limit=10)

        current_cvd = self.CVD.get(symbol, 0.0)
        prev_cvd = self.get_prev_cvd(symbol)

        oi_delta = self.get_oi_delta(symbol)

        prev_close = df['close'].iloc[-2]

        signal_result = analyze_signal(
            df,
            cvd=current_cvd,
            oi_delta=oi_delta,
            prev_close=prev_close,
            prev_cvd=prev_cvd
        )

        return signal_result
