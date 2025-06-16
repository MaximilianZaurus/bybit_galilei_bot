# bybit_client.py
from pybit.unified_trading import HTTP, WebSocket

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

http = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
ws = WebSocket(testnet=False, subscriptions=[])
