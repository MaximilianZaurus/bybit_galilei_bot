import os
import requests
import asyncio
import logging
import json
import websockets
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"

logging.basicConfig(level=logging.INFO)


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logging.error(f"Telegram error: {response.text}")
    except Exception as e:
        logging.error(f"Telegram exception: {e}")


def get_funding_rate(symbol):
    url = f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={symbol}&limit=1"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logging.error(f"Funding rate HTTP error {symbol}: {resp.status_code} {resp.text}")
            return None

        logging.info(f"Funding rate raw response for {symbol}: {resp.text}")
        data = resp.json()

        if data.get("retCode") != 0 or not data["result"]["list"]:
            logging.error(f"Funding rate no data {symbol}: {data}")
            return None

        return float(data["result"]["list"][0]["fundingRate"])
    except Exception as e:
        logging.error(f"Funding rate exception {symbol}: {e}")
        return None


def get_open_interest(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logging.error(f"Open interest HTTP error {symbol}: {resp.status_code} {resp.text}")
            return None

        logging.info(f"Open interest raw response for {symbol}: {resp.text}")
        data = resp.json()

        if data.get("retCode") != 0 or not data["result"]["list"]:
            logging.error(f"Open interest no data {symbol}: {data}")
            return None

        return float(data["result"]["list"][0]["openInterest"])
    except Exception as e:
        logging.error(f"Open interest exception {symbol}: {e}")
        return None


async def websocket_listener():
    topics = [f"liquidation.{symbol}" for symbol in SYMBOLS]
    subscribe_msg = json.dumps({
        "op": "subscribe",
        "args": topics
    })

    try:
        async with websockets.connect(BYBIT_WS_URL) as ws:
            await ws.send(subscribe_msg)
            logging.info(f"Subscribed to WS: {topics}")

            while True:
                message = await ws.recv()
                data = json.loads(message)
                if "data" in data:
                    for item in data["data"]:
                        symbol = item.get("symbol")
                        side = item.get("side")
                        price = item.get("price")
                        size = item.get("qty")
                        msg = f"💥 Liquidation Alert\nSymbol: {symbol}\nSide: {side}\nPrice: {price}\nSize: {size}"
                        send_telegram_message(msg)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")


async def periodic_task():
    while True:
        for symbol in SYMBOLS:
            fr = get_funding_rate(symbol)
            oi = get_open_interest(symbol)
            if fr is not None and oi is not None:
                msg = f"📊 *{symbol}*\nFunding Rate: {fr:.6f}\nOpen Interest: {oi:.2f}"
                send_telegram_message(msg)
        await asyncio.sleep(60 * 30)  # каждые 30 минут


async def main():
    listener_task = asyncio.create_task(websocket_listener())
    periodic_task_ = asyncio.create_task(periodic_task())
    await asyncio.gather(listener_task, periodic_task_)


if __name__ == "__main__":
    logging.info("Bot started")
    asyncio.run(main())

