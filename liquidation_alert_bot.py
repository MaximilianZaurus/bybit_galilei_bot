import asyncio
import logging
import aiohttp
import websockets
import json
from datetime import datetime
import os

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# API V5
FUNDING_URL = "https://api.bybit.com/v5/market/funding/history"
OPEN_INTEREST_URL = "https://api.bybit.com/v5/market/open-interest"
WS_URL = "wss://stream.bybit.com/v5/public/linear"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

async def fetch_funding_rate(session, symbol):
    try:
        params = {"category": "linear", "symbol": symbol, "limit": 1}
        async with session.get(FUNDING_URL, params=params) as response:
            data = await response.json()
            rate = float(data['result']['list'][0]['fundingRate'])
            return rate
    except Exception as e:
        logging.error(f"Funding rate error {symbol}: {e}")
        return None

async def fetch_open_interest(session, symbol):
    try:
        params = {"category": "linear", "symbol": symbol, "intervalTime": "60"}
        async with session.get(OPEN_INTEREST_URL, params=params) as response:
            data = await response.json()
            if data.get("retCode") == 0 and data["result"]["list"]:
                value = float(data["result"]["list"][0]["openInterest"])
                return value
            else:
                logging.error(f"Open interest response for {symbol}: {data}")
    except Exception as e:
        logging.error(f"Open interest error {symbol}: {e}")
    return None

async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, data={"chat_id": CHAT_ID, "text": text})

async def monitor_funding_and_interest():
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            rate = await fetch_funding_rate(session, symbol)
            oi = await fetch_open_interest(session, symbol)
            if rate is not None and oi is not None:
                text = f"\n📊 {symbol}\nFunding Rate: {rate:.6f}\nOpen Interest: {oi:,.2f}"
                await send_telegram_message(text)

async def listen_liquidations():
    async with websockets.connect(WS_URL) as ws:
        sub_msg = {
            "op": "subscribe",
            "args": [f"liquidation.{symbol}" for symbol in SYMBOLS]
        }
        await ws.send(json.dumps(sub_msg))

        while True:
            message = await ws.recv()
            data = json.loads(message)
            if data.get("topic", "").startswith("liquidation"):
                for entry in data.get("data", []):
                    symbol = entry.get("symbol")
                    price = entry.get("price")
                    side = entry.get("side")
                    size = entry.get("qty")
                    text = f"💥 Liquidation on {symbol}: {side} {size} at {price}"
                    await send_telegram_message(text)

async def main():
    logging.info("Bot started")
    await monitor_funding_and_interest()
    await listen_liquidations()

if __name__ == "__main__":
    asyncio.run(main())
