import httpx
import pandas as pd
from ta.trend import ADXIndicator, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import AwesomeOscillatorIndicator

BYBIT_URL = "https://api.bybit.com/v5/market/kline"
TICKERS = [
    "BTCUSDT", "ETHUSDT", "AAVEUSDT", "SOLUSDT", "XMRUSDT",
    "TONUSDT", "NEARUSDT", "LTCUSDT", "APTUSDT", "WLDUSDT"
]

async def fetch_klines(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    try:
        async with httpx.AsyncClient() as client:
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            response = await client.get(BYBIT_URL, params=params)
            data = response.json()

            if "result" not in data or "list" not in data["result"]:
                print(f"⚠️ Некорректный ответ от API Bybit для {symbol}: {data}")
                return pd.DataFrame()

            df = pd.DataFrame(data["result"]["list"], columns=[
                "timestamp", "open", "high", "low", "close", "volume", "turnover"
            ])

            if df.empty:
                print(f"⚠️ Пустой DataFrame от Bybit для {symbol}")
                return df

            df = df.iloc[::-1]  # переворачиваем порядок: от старого к новому
            df["close"] = pd.to_numeric(df["close"])
            df["high"] = pd.to_numeric(df["high"])
            df["low"] = pd.to_numeric(df["low"])
            df["open"] = pd.to_numeric(df["open"])
            return df.reset_index(drop=True)

    except Exception as e:
        print(f"❌ Ошибка при получении данных для {symbol}: {e}")
        return pd.DataFrame()

async def analyze_ticker(symbol: str, df: pd.DataFrame) -> str:
    if df.empty or len(df) < 2:
        return f"⚠️ Недостаточно данных для анализа {symbol}.\n"

    try:
        last_close = df["close"].iloc[-1]

        # Пример использования индикаторов (можно расширить под стратегию)
        adx = ADXIndicator(df["high"], df["low"], df["close"]).adx()
        bb = BollingerBands(df["close"])
        ao = AwesomeOscillatorIndicator(df["high"], df["low"]).awesome_oscillator()
        psar = PSARIndicator(df["high"], df["low"], df["close"]).psar()

        message = (
            f"📈 Сигналы для {symbol}:\n"
            f"• Закрытие: {last_close:.2f}\n"
            f"• ADX: {adx.iloc[-1]:.2f}\n"
            f"• AO: {ao.iloc[-1]:.2f}\n"
            f"• SAR: {psar.iloc[-1]:.2f}\n"
            f"• BB верх/низ: {bb.bollinger_hband().iloc[-1]:.2f} / {bb.bollinger_lband().iloc[-1]:.2f}\n"
        )
        return message

    except Exception as e:
        return f"❌ Ошибка анализа {symbol}: {e}\n"
