import os
import asyncio
import json
import logging
from collections import defaultdict
from pybit.unified_trading import HTTP, WebSocket
import pandas as pd
from signals import analyze_signal

logger = logging.getLogger(__name__)
CVD_FILE = "cvd_data.json"

TIMEFRAMES = {
    "15m": "15",
    "1h": "60"
}

class BybitClient:
    def __init__(self):
        API_KEY = os.getenv("BYBIT_API_KEY")
        API_SECRET = os.getenv("BYBIT_API_SECRET")

        self.category = "linear"
        self.http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
        self.ws = WebSocket(testnet=False, channel_type=self.category)

        self.CVD = defaultdict(float, self.load_cvd_data())
        self.OI_HISTORY = defaultdict(list)

        # Убрано: self.ws.on("trade", self.handle_message)

    def load_cvd_data(self) -> dict:
        if os.path.exists(CVD_FILE):
            try:
                with open(CVD_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded CVD from file: {data}")
                    return {symbol: float(value) for symbol, value in data.items()}
            except Exception as e:
                logger.error(f"Error loading CVD: {e}")
        return {}

    def save_cvd_data(self):
        try:
            with open(CVD_FILE, "w", encoding="utf-8") as f:
                json.dump(self.CVD, f, ensure_ascii=False, indent=2)
                logger.debug(f"CVD saved to file: {self.CVD}")
        except Exception as e:
            logger.error(f"Error saving CVD: {e}")

    def get_prev_cvd(self, symbol: str) -> float:
        return self.CVD.get(symbol, 0.0)

    def update_prev_cvd(self, symbol: str, value: float):
        self.CVD[symbol] = value
        self.save_cvd_data()

    async def start_ws(self):
        logger.info("WebSocket in pybit v5 starts automatically.")

    def subscribe_to_trades(self, tickers):
        if not isinstance(tickers, list):
            logger.error(f"Expected list of tickers, got {type(tickers)}")
            raise TypeError("tickers must be a list")
        if any(not isinstance(t, str) for t in tickers):
            logger.error("All tickers must be strings")
            raise TypeError("All tickers must be strings")

        logger.info(f"Subscribing to trades: {tickers}")
        self.ws.subscribe(
            topic="trade",
            symbol=tickers,
            callback=self.handle_message
        )
        logger.info("Subscriptions sent")

    def handle_message(self, msg):
        topic = msg.get("topic", "")
        data = msg.get("data", [])
        if topic.startswith("trade."):
            symbol = topic.split(".")[1]
            for trade in data:
                qty = float(trade['qty'])
                side = trade['side']
                if side == "Buy":
                    self.CVD[symbol] += qty
                elif side == "Sell":
                    self.CVD[symbol] -= qty

    async def get_current_price(self, symbol: str) -> float:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: self.http.get_tickers(category=self.category))
        logger.debug(f"get_tickers response: {resp}")

        if not resp or not isinstance(resp, dict):
            raise ValueError(f"Empty or invalid response from get_tickers: {resp}")

        result = resp.get('result')
        if not result or not isinstance(result, dict) or 'list' not in result or not isinstance(result['list'], list):
            raise ValueError(f"Invalid get_tickers result format: {resp}")

        for ticker in result['list']:
            sym = ticker.get('symbol', '').upper()
            last_price = ticker.get('lastPrice') or ticker.get('last_price')
            if sym == symbol.upper() and last_price is not None:
                return float(last_price)

        raise ValueError(f"Price not found for {symbol}")

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

    def get_oi_delta(self, symbol: str) -> float:
        # Предполагается, что логика получения delta Open Interest реализована
        if symbol not in self.OI_HISTORY or len(self.OI_HISTORY[symbol]) < 2:
            return 0.0
        return self.OI_HISTORY[symbol][-1] - self.OI_HISTORY[symbol][-2]
