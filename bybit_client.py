import os
import threading
from collections import defaultdict
import asyncio
from pybit.unified_trading import HTTP, WebSocket

class BybitClient:
    def __init__(self):
        API_KEY = os.getenv("BYBIT_API_KEY")
        API_SECRET = os.getenv("BYBIT_API_SECRET")

        self.http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
        self.ws = WebSocket(testnet=False, channel_type="linear")  # или "inverse"
        
        self.CVD = defaultdict(float)
        self.OI_HISTORY = defaultdict(list)

        self.ws.callback = self.handle_message
        self.ws_thread = None

    def fetch_open_interest(self, symbol: str) -> float:
        resp = self.http.get_open_interest(symbol=symbol)
        return float(resp['result']['open_interest'])

    def update_oi_history(self, symbol: str):
        oi = self.fetch_open_interest(symbol)
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
        # msg — dict с данными от WS
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
        resp = await loop.run_in_executor(None, self.http.get_tickers, symbol)
        if resp and 'result' in resp and len(resp['result']) > 0:
            return float(resp['result'][0]['lastPrice'])
        else:
            raise ValueError(f"Не удалось получить цену для {symbol}")
