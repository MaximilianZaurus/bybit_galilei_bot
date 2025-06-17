import os
import threading
from collections import defaultdict
import asyncio
import logging
from pybit.unified_trading import HTTP, WebSocket

logger = logging.getLogger(__name__)

class BybitClient:
    def __init__(self):
        API_KEY = os.getenv("BYBIT_API_KEY")
        API_SECRET = os.getenv("BYBIT_API_SECRET")

        self.category = "linear"  # "linear" для USDⓈ-M, "inverse" для COIN-M

        self.http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
        self.ws = WebSocket(testnet=False, channel_type=self.category)
        
        self.CVD = defaultdict(float)
        self.OI_HISTORY = defaultdict(list)

        self.ws.callback = self.handle_message
        self.ws_thread = None

    async def fetch_open_interest(self, symbol: str) -> float:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: self.http.get_open_interest(symbol=symbol, category=self.category))
        if resp.get('result') and 'open_interest' in resp['result']:
            return float(resp['result']['open_interest'])
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
        for topic, data in msg.items():
            if topic.startswith("trade."):
                symbol = topic.split(".")[1]
                for t in data:
                    qty = float(t['qty'])
                    side = t['side']
                    self.CVD[symbol] += qty if side == 'Buy' else -qty

    def subscribe_to_trades(self, symbols: list):
        topics = [f"trade.{sym}" for sym in symbols]
        self.ws.subscribe(topics)

    def start_ws(self):
        if self.ws_thread and self.ws_thread.is_alive():
            return
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()

    async def get_current_price(self, symbol: str) -> float:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: self.http.get_tickers(category=self.category))
        logger.debug(f"Ответ get_tickers: {resp}")

        if not resp or not isinstance(resp, dict):
            raise ValueError(f"Пустой или неверный ответ от API get_tickers: {resp}")

        if 'result' not in resp or not isinstance(resp['result'], list):
            raise ValueError(f"В ответе отсутствует поле 'result' или оно не список: {resp}")

        for ticker in resp['result']:
            if not isinstance(ticker, dict):
                continue
            sym = ticker.get('symbol', '').upper()
            last_price = ticker.get('lastPrice') or ticker.get('last_price')
            logger.debug(f"Проверяем тикер: {sym} с ценой: {last_price}")
            if sym == symbol.upper() and last_price is not None:
                try:
                    return float(last_price)
                except Exception as e:
                    logger.error(f"Ошибка конвертации цены в float для {symbol}: {e}")
                    raise

        raise ValueError(f"Не удалось получить цену для {symbol}")

    async def get_klines(self, symbol: str, interval: str, limit: int = 200):
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
