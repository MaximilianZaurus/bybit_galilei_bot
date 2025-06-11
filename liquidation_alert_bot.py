import asyncio
import json
import logging
import os
import requests
import websockets

logging.basicConfig(level=logging.INFO)

# Конфиги
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # передай через env
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_API_BASE = "https://api.bybit.com"
BYBIT_WS_URL = "wss://stream.bybit.com/realtime_public/v5"

SYMBOLS = ["BTCUSDT", "AAVEUSDT", "ETHUSDT", "SOLUSDT", "XMRUSDT"]

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Отправка сообщения в Telegram
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    resp = requests.post(url, json=data)
    if resp.status_code == 200:
        logging.info("Telegram message sent.")
    else:
        logging.error(f"Telegram send error: {resp.text}")

# Получить ликвидации
def fetch_liquidations(symbol):
    url = f"{BYBIT_API_BASE}/v5/market/liquidation-records"
    params = {
        "category": "linear",
        "symbol": symbol,
        "limit": 10
    }
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        logging.error(f"Liquidations error {symbol}: {resp.text}")
        return None
    data = resp.json()
    if data.get("retCode") != 0:
        logging.error(f"Liquidations error {symbol}: {data}")
        return None
    return data["result"]["list"]

# Получить funding rate
def fetch_funding_rate(symbol):
    url = f"{BYBIT_API_BASE}/v5/market/funding-rate"
    params = {
        "category": "linear",
        "symbol": symbol
    }
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        logging.error(f"Funding rate error {symbol}: {resp.text}")
        return None
    data = resp.json()
    if data.get("retCode") != 0:
        logging.error(f"Funding rate error {symbol}: {data}")
        return None
    return data["result"]["fundingRate"]

# Получить open interest
def fetch_open_interest(symbol):
    url = f"{BYBIT_API_BASE}/v5/market/open-interest"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "1h"  # Обязательный параметр!
    }
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        logging.error(f"Open interest error {symbol}: {resp.text}")
        return None
    data = resp.json()
    if data.get("retCode") != 0 or not data.get("result") or not data["result"].get("list"):
        logging.error(f"Open interest no data for {symbol}: {data}")
        return None
    # Возвращаем последний по времени openInterest
    return float(data["result"]["list"][-1]["openInterest"])

# Обработка данных и отправка в Telegram
def analyze_and_notify():
    for symbol in SYMBOLS:
        liquidations = fetch_liquidations(symbol)
        funding_rate = fetch_funding_rate(symbol)
        open_interest = fetch_open_interest(symbol)
        if liquidations is None or funding_rate is None or open_interest is None:
            continue

        # Анализ (примитивный, можешь расширять)
        big_liq_count = sum(1 for liq in liquidations if float(liq["qty"]) > 1000)
        msg = (
            f"Symbol: {symbol}\n"
            f"Big Liquidations (qty > 1000): {big_liq_count}\n"
            f"Funding Rate: {funding_rate}\n"
            f"Open Interest (1h): {open_interest}\n"
        )
        send_telegram_message(msg)

# WebSocket слушатель ликвидаций
async def websocket_listener():
    async with websockets.connect(BYBIT_WS_URL) as ws:
        # Подписываемся на ликвидации
        args = [f"liquidation.1.{sym}" for sym in SYMBOLS]
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        await ws.send(json.dumps(subscribe_msg))
        logging.info(f"Subscribed to WS channels: {args}")

        async for message in ws:
            data = json.loads(message)
            if "topic" in data and "data" in data:
                topic = data["topic"]
                payload = data["data"]
                logging.info(f"WS {topic} data: {payload}")
                # Можно добавить фильтр и отправку в Telegram по крупным ликвидациям

async def periodic_task():
    while True:
        analyze_and_notify()
        await asyncio.sleep(300)  # раз в 5 минут

async def main():
    listener_task = asyncio.create_task(websocket_listener())
    periodic_task_ = asyncio.create_task(periodic_task())
    await asyncio.gather(listener_task, periodic_task_)

if __name__ == "__main__":
    logging.info("Bot started")
    asyncio.run(main())
