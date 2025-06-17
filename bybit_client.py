from pybit.unified_trading import HTTP, WebSocket
import os
from collections import defaultdict
import threading

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
ws = WebSocket(testnet=False, channel_type="linear")  # <--- обязательно указать channel_type

CVD = defaultdict(float)
OI_HISTORY = defaultdict(list)

def fetch_open_interest(symbol: str) -> float:
    resp = http.get_open_interest(symbol=symbol)
    return float(resp['result']['open_interest'])

def update_oi_history(symbol: str):
    oi = fetch_open_interest(symbol)
    history = OI_HISTORY[symbol]
    history.append(oi)
    if len(history) > 3:
        history.pop(0)

def get_oi_delta(symbol: str) -> float:
    history = OI_HISTORY[symbol]
    if len(history) < 3:
        return 0.0
    return history[-1] - history[0]

def handle_message(msg):
    # msg — dict с данными от WS
    for topic, data in msg.items():
        if topic.startswith("trade."):
            symbol = topic.split(".")[1]
            for t in data:
                qty = float(t['qty'])
                side = t['side']
                CVD[symbol] += qty if side == 'Buy' else -qty

def subscribe_to_trades(symbols: list):
    topics = [f"trade.{sym}" for sym in symbols]
    ws.subscribe(topics)
    ws.callback = handle_message  # или ws.set_callback(handle_message) если нужно

def start_ws():
    t = threading.Thread(target=ws.run_forever)
    t.daemon = True
    t.start()
