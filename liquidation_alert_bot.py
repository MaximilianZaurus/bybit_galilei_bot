import asyncio
import json
import logging
import requests
from telegram import Bot
from collections import deque
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = "8054456169:AAFam6kFVbW6GJFZjNCip18T-geGUAk4kwA"
TELEGRAM_CHAT_ID = "5309903897"
bot = Bot(token=TELEGRAM_TOKEN)

BYBIT_WS_URL = "wss://stream.bybit.com/realtime_public"
SYMBOLS = ["BTCUSDT", "AAVEUSDT", "ETHUSDT", "SOLUSDT", "XMRUSDT"]
BYBIT_API_BASE = "https://api.bybit.com"
HEADERS = {"Accept": "application/json"}

# Порог объема ликвидаций для алерта (настрой по желанию)
LIQUIDATION_VOLUME_THRESHOLD = {
    "BTCUSDT": 5,     # в BTC
    "AAVEUSDT": 100,  # в AAVE
    "ETHUSDT": 20,
    "SOLUSDT": 500,
    "XMRUSDT": 200
}

# Для хранения ликвидаций за последние 5 минут
liquidations_data = {sym: deque() for sym in SYMBOLS}  # [(timestamp, qty), ...]

async def send_telegram_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logging.info("Telegram message sent")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

def fetch_funding_rate(symbol):
    url = f"{BYBIT_API_BASE}/v5/market/funding/history?category=linear&symbol={symbol}&limit=1"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        logging.error(f"Funding rate error {symbol}: {resp.text}")
        return None
    data = resp.json()
    if data.get("retCode") != 0 or not data.get("result") or not data["result"].get("list"):
        logging.error(f"Funding rate no data for {symbol}: {data}")
        return None
    return float(data["result"]["list"][0]["fundingRate"])

def fetch_open_interest(symbol):
    # Исправлен параметр interval на '5m'
    url = f"{BYBIT_API_BASE}/v5/market/open-interest?category=linear&symbol={symbol}&interval=5m"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        logging.error(f"Open interest error {symbol}: {resp.text}")
        return None
    data = resp.json()
    if data.get("retCode") != 0 or not data.get("result") or not data["result"].get("list"):
        logging.error(f"Open interest no data for {symbol}: {data}")
        return None
    return float(data["result"]["list"][-1]["openInterest"])

async def process_liquidation_message(data):
    topic = data.get("topic", "")
    if not topic.startswith("liquidation."):
        return
    symbol = topic.split(".")[1]
    now = datetime.utcnow()
    for liq in data.get("data", []):
        qty = float(liq.get("qty", 0))
        price = liq.get("price")
        side = liq.get("side")
        timestamp = datetime.utcfromtimestamp(liq.get("trade_time_ms", 0)/1000) if liq.get("trade_time_ms") else now
        # Добавляем в очередь ликвидаций
        liquidations_data[symbol].append((timestamp, qty))
        logging.info(f"Liquidation {symbol}: side={side} price={price} qty={qty} time={timestamp}")

async def cleanup_old_liquidations():
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    for symbol in SYMBOLS:
        while liquidations_data[symbol] and liquidations_data[symbol][0][0] < cutoff:
            liquidations_data[symbol].popleft()

def check_and_alert_liquidations():
    alerts = []
    for symbol in SYMBOLS:
        total_qty = sum(qty for ts, qty in liquidations_data[symbol])
        threshold = LIQUIDATION_VOLUME_THRESHOLD.get(symbol, 1000)
        if total_qty >= threshold:
            alerts.append(f"⚠️ Ликвидации за последние 5 мин по {symbol}: {total_qty:.2f} (порог {threshold})")
            # Очистим после алерта, чтобы не спамить
            liquidations_data[symbol].clear()
    return alerts

async def websocket_listener():
    import websockets
    reconnect_delay = 5
    while True:
        try:
            async with websockets.connect(BYBIT_WS_URL) as ws:
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [f"liquidation.{sym}" for sym in SYMBOLS]
                }
                await ws.send(json.dumps(subscribe_msg))
                logging.info(f"Subscribed to liquidation channels: {subscribe_msg['args']}")
                async for message in ws:
                    data = json.loads(message)
                    await process_liquidation_message(data)
        except Exception as e:
            logging.error(f"WebSocket error: {e}")
            await asyncio.sleep(reconnect_delay)

async def rest_data_loop():
    while True:
        messages = []
        for symbol in SYMBOLS:
            fr = fetch_funding_rate(symbol)
            oi = fetch_open_interest(symbol)
            if fr is None or oi is None:
                messages.append(f"{symbol}: Ошибка получения данных.")
            else:
                messages.append(f"{symbol}:\nFunding Rate: {fr:.6%}\nOpen Interest: {oi:.0f}")

        # Проверяем ликвидации и формируем алерты
        await cleanup_old_liquidations()
        liquidation_alerts = check_and_alert_liquidations()
        messages.extend(liquidation_alerts)

        if messages:
            await send_telegram_message("\n\n".join(messages))
        await asyncio.sleep(300)  # 5 минут

async def main():
    listener_task = asyncio.create_task(websocket_listener())
    rest_task = asyncio.create_task(rest_data_loop())
    await asyncio.gather(listener_task, rest_task)

if __name__ == "__main__":
    logging.info("Bot started")
    asyncio.run(main())
