import os
import json
import asyncio
import logging
from collections import defaultdict
from pybit.unified_trading import HTTP, WebSocket

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

        self.category = "linear"  # USDⓈ-M фьючерсы
        self.http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
        self.ws = WebSocket(testnet=False, channel_type=self.category)

        self.CVD = defaultdict(float, self.load_cvd_data())
        self.OI_HISTORY = defaultdict(list)

    # --- CVD JSON persistence ---

    def load_cvd_data(self) -> dict:
        if os.path.exists(CVD_FILE):
            try:
                with open(CVD_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Загружены CVD из файла: {data}")
                    return {symbol: float(value) for symbol, value in data.items()}
            except Exception as e:
                logger.error(f"Ошибка при загрузке CVD: {e}")
        return {}

    def save_cvd_data(self):
        try:
            with open(CVD_FILE, "w", encoding="utf-8") as f:
                json.dump(self.CVD, f, ensure_ascii=False, indent=2)
                logger.debug(f"CVD сохранены в файл: {self.CVD}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении CVD: {e}")

    def get_prev_cvd(self, symbol: str) -> float:
        return self.CVD.get(symbol, 0.0)

    def update_prev_cvd(self, symbol: str, value: float):
        self.CVD[symbol] = value
        self.save_cvd_data()

    # --- Основной функционал ---

    async def fetch_open_interest(self, symbol: str) -> float:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self.http.get_open_interest(symbol=symbol, category=self.category)
        )
        if resp.get('result') and 'openInterest' in resp['result']:
            return float(resp['result']['openInterest'])
        raise ValueError(f"Ошибка получения open interest для {symbol}: {resp}")

    async def update_oi_history(self, symbol: str):
        oi = await self.fetch_open_interest(symbol)
        history = self.OI_HISTORY[symbol]
        history.append(oi)
        if len(history) > 3:
            history.pop(0)

    def get_oi_delta(self, symbol: str) -> float:
        history = self.OI_HISTORY[symbol]
        if len(history) < 3:
            return 0.0
        return history[-1] - history[0]

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

    def subscribe_to_trades(self, tickers: list):
        if not isinstance(tickers, list):
            raise TypeError("tickers must be a list")
        logger.info(f"Подписка на тикеры: {tickers}")
        for ticker in tickers:
            self.ws.subscribe(
                topic="trade",
                symbol=ticker,
                callback=self.handle_message
            )

    async def start_ws(self):
        await self.ws.connect()
        await self.ws.run()

    async def get_current_price(self, symbol: str) -> float:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: self.http.get_tickers(category=self.category))
        logger.debug(f"Ответ get_tickers: {resp}")

        if not resp or not isinstance(resp, dict):
            raise ValueError(f"Пустой или неверный ответ от API get_tickers: {resp}")

        result = resp.get('result')
        if not result or not isinstance(result, dict) or 'list' not in result or not isinstance(result['list'], list):
            raise ValueError(f"Неверный формат результата get_tickers: {resp}")

        for ticker in result['list']:
            sym = ticker.get('symbol', '').upper()
            last_price = ticker.get('lastPrice') or ticker.get('last_price')
            if sym == symbol.upper() and last_price is not None:
                return float(last_price)

        raise ValueError(f"Не удалось найти цену для {symbol}")

    async def get_klines(self, symbol: str, interval: str, limit: int = 200):
        allowed_intervals = {"1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M"}
        if interval not in allowed_intervals:
            raise ValueError(f"Неверный interval для get_kline: {interval}")

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: self.http.get_kline(
            symbol=symbol,
            interval=interval,
            limit=limit,
            category=self.category
        ))

        if resp and isinstance(resp, dict) and 'result' in resp and 'list' in resp['result']:
            return resp['result']['list']
        else:
            raise ValueError(f"Ошибка получения свечей для {symbol}: {resp}")
