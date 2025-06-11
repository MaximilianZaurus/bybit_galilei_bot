import asyncio
import logging
import os
import aiohttp
import json
import websockets
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
BYBIT_HTTP_URL = "https://api.bybit.com"

async def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Telegram error: {await resp.text()}")
    except Exception as e:
        logger.error(f"Telegram exception: {e}")

async def fetch_funding_rate(symbol):
    try:
        url = f"{BYBIT_HTTP_URL}/v5/market/funding-rate?symbol={symbol}&category=linear"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                raw = await resp.text()
                logger.info(f"Funding rate raw response for {symbol}: {raw}")
                data = json.loads(raw)
                rate = float(data["result"]["list"][0]["fundingRate"])
                return rate
    except Exception as e:
        logger.error(f"Funding rate error {symbol}: {e}")
        return None

async def fetch_open_interest(symbol):
    try:
        url = f"{BYBIT_HTTP_URL}/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min&limit=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                raw = await resp.text()
                logger.info(f"Open interest raw response for {symbol}: {raw}")
                data = json.loads(raw)
                if not data["result"]["list"]:
                    logger.error(f"Open interest no data {symbol}: {data}")
                    return None
                oi_value = float(data["result"]["list"][0]["openInterest"])
                return oi_value
    except Exception as e:
        logger.error(f"Open interest error {symbol}: {e}")
        return None

async def periodic_metrics():
    while True:
        for symbol in SYMBOLS:
            rate = await fetch_funding_rate(symbol)
            oi = await fetch_open_interest(symbol)
            if rate is not None and oi is not None:
                message = f"🔄 {symbol}\nFunding Rate: {rate:.6f}\nOpen Interest: {oi:.2f}"
                await send_telegram_message(message)
        await asyncio.sleep(600)  # каждые 10 минут

async def websocket_listener():
    try:
        async with websockets.connect(BYBIT_WS_URL) as ws:
            topics = [f"liquidation.{s}" for s in SYMBOLS]
            await ws.send(json.dumps({"op": "subscribe", "args": topics}))
            logger.info(f"Subscribed to WS: {topics}")

            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("topic", "").startswith("liquidation."):
                    symbol = data["topic"].split(".")[1]
                    for event in data.get("data", []):
                        side = event.get("side")
                        price = event.get("price")
                        qty = event.get("qty")
                        message = (
                            f"💥 Liquidation Alert\n{symbol}\nSide: {side}\nPrice: {price}\nQty: {qty}"
                        )
                        await send_telegram_message(message)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def main():
    logger.info("Bot started")
    listener_task = asyncio.create_task(websocket_listener())
    periodic_task_ = asyncio.create_task(periodic_metrics())
    await asyncio.gather(listener_task, periodic_task_)

if __name__ == "__main__":
    asyncio.run(main())
