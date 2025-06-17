from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

client = HTTP(
    testnet=False,
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)
