import os
from collections import defaultdict
import asyncio
import logging
from pybit.unified_trading import HTTP, WebSocket

logger = logging.getLogger(__name__)

class BybitClient:
    def __init__(self):
        API_KEY = os.getenv("BYBIT_API_KEY")
        API_SECRET = os.getenv("BYBIT_API_SECRET")

        self.category = "linear"  # USDⓈ-M фьючерсы
        self.http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
        self.ws = WebSocket(testnet=False, channel_type=self.category)

        self.CVD = defaultdict(float)         # cumulative volume delta (накопленный дельта-объём)
        self.OI_HISTORY = defaultdict(list)   # история open interest

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
                side = trade['side']  # "Buy" или "Sell"
                if side == "Buy":
                    self.CVD[symbol] += qty
                elif side == "Sell":
                    self.CVD[symbol] -= qty

    def subscribe_to_trades(self, symbols: list):
        topics = [f"trade.{sym}" for sym in symbols]
        self.ws.subscribe(topics, self.handle_message)  # Обязательно передаем callback

    async def start_ws(self):
        await self.ws.connect()
        # В pybit v5 нет run_forever, а есть run() — слушаем сообщения
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
