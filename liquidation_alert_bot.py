import asyncio
import logging
import json
import os
import requests
import websockets
from datetime import datetime

# Настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
BYBIT_REST_URL = "https://api.bybit.com"

logging.basicConfig(level=logging.INFO)

# Уведомление в Telegram
def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logging.error(f"Telegram error: {response.text}")
        else:
            logging.info("Telegram message sent")
    except Exception as e:
        logging.error(f"Telegram exception: {e}")

# Получение funding rate и open interest
def fetch_funding_and_oi(symbol: str):
    messages = []

    try:
        r1 = requests.get(f"{BYBIT_REST_URL}/v5/market/funding-rate", params={
            "category": "linear", "symbol": symbol
        })
        data = r1.json()
        rate = float(data["result"]["list"][0]["fundingRate"]) * 100
        messages.append(f"🔁 Funding Rate for <b>{symbol}</b>: {rate:.4f}%")
    except Exception as e:
        logging.error(f"Funding rate error {symbol}: {e}")

    try:
        r2 = requests.get(f"{BYBIT_REST_URL}/v5/market/open-interest", params={
            "category": "linear", "symbol": symbol, "intervalTime": "5"
        })
        data = r2.json()
        oi = float(data["result"]["list"][-1]["openInterest"])
        messages.append(f"📊 Open Interest for <b>{symbol}</b>: {oi:.2f}")
    except Exception as e:
        logging.error(f"Open interest error {symbol}: {e}")

    return "\n".join(messages)

# Периодический REST-запрос
async def periodic_metrics():
    while True:
        full_message = "📈 <b>Funding Rate & Open Interest</b>\n\n"
        for symbol in SYMBOLS:
            data = fetch_funding_and_oi(symbol)
            if data:
                full_message += data + "\n\n"
        send_telegram_message(full_message.strip())
        await asyncio.sleep(3600)  # 1 час

# WebSocket слушатель ликвидаций
async def websocket_listener():
    async with websockets.connect(BYBIT_WS_URL) as ws:
        args = [f"liquidation.{s}" for s in SYMBOLS]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))
        logging.info(f"Subscribed to WS: {args}")

        async for msg in ws:
            data = json.loads(msg)
            if "data" in data and "topic" in data:
                info = data["data"]
                symbol = info["symbol"]
                side = info["side"]
                price = float(info["price"])
                qty = float(info["qty"])
                value = float(info["value"])
                ts = datetime.utcfromtimestamp(info["ts"] / 1000).strftime("%Y-%m-%d %H:%M:%S")

                if value > 50000:  # Фильтр по сумме ликвидации
                    emoji = "🔴" if side == "Sell" else "🟢"
                    message = (
                        f"{emoji} <b>Liquidation Alert</b>\n"
                        f"Symbol: <b>{symbol}</b>\n"
                        f"Side: <b>{side}</b>\n"
                        f"Qty: {qty}\n"
                        f"Price: {price}\n"
                        f"💰 Value: <b>${value:,.0f}</b>\n"
                        f"UTC Time: {ts}"
                    )
                    send_telegram_message(message)

# Запуск
async def main():
    logging.info("Bot started")
    listener = asyncio.create_task(websocket_listener())
    rest_task = asyncio.create_task(periodic_metrics())
    await asyncio.gather(listener, rest_task)

if __name__ == "__main__":
    asyncio.run(main())
