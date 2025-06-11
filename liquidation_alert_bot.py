import os
import json
import logging
import requests
import threading
import time
import websocket

from telegram import Bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Читаем переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    logging.error("TELEGRAM_TOKEN и TELEGRAM_CHAT_ID должны быть заданы в переменных окружения")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]

# URL для получения funding rate и open interest с обязательным параметром intervalTime для open interest
FUNDING_RATE_URL = "https://api.bybit.com/derivatives/v3/public/funding-rate"
OPEN_INTEREST_URL = "https://api.bybit.com/derivatives/v3/public/open-interest"

# Интервал для open interest (нужен параметр, допустим, 60 секунд)
OPEN_INTEREST_INTERVAL = 60

def get_funding_rate(symbol):
    try:
        params = {"symbol": symbol}
        response = requests.get(FUNDING_RATE_URL, params=params)
        data = response.json()
        logging.info(f"Funding rate raw response for {symbol}: {json.dumps(data)}")
        if data.get("retCode") == 0:
            lst = data.get("result", {}).get("list", [])
            if lst:
                return float(lst[0].get("fundingRate", 0))
        else:
            logging.error(f"Funding rate error {symbol}: {data.get('retMsg')}")
    except Exception as e:
        logging.error(f"Funding rate exception {symbol}: {e}")
    return None

def get_open_interest(symbol):
    try:
        params = {
            "symbol": symbol,
            "intervalTime": OPEN_INTEREST_INTERVAL  # обязательный параметр для API
        }
        response = requests.get(OPEN_INTEREST_URL, params=params)
        data = response.json()
        logging.info(f"Open interest raw response for {symbol}: {json.dumps(data)}")
        if data.get("retCode") == 0:
            lst = data.get("result", {}).get("list", [])
            if lst:
                # В зависимости от формата API, берем нужное поле, например openInterest
                return float(lst[0].get("openInterest", 0))
            else:
                logging.error(f"Open interest no data {symbol}: {data}")
        else:
            logging.error(f"Open interest error {symbol}: {data.get('retMsg')}")
    except Exception as e:
        logging.error(f"Open interest exception {symbol}: {e}")
    return None

def send_telegram_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Telegram error: {e}")

def on_message(ws, message):
    try:
        data = json.loads(message)
        # Пример обработки входящего сообщения
        if "data" in data:
            for item in data["data"]:
                symbol = item.get("symbol")
                price = item.get("price")
                side = item.get("side")
                quantity = item.get("quantity")
                text = f"Ликвидация {symbol}: {side} {quantity} @ {price}"
                logging.info(text)
                send_telegram_message(text)
    except Exception as e:
        logging.error(f"WebSocket message handler error: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.info(f"WebSocket closed: {close_status_code} - {close_msg}")

def on_open(ws):
    logging.info("WebSocket connection opened")
    # Подписываемся на каналы ликвидаций
    params = {
        "op": "subscribe",
        "args": [f"liquidation.{symbol}" for symbol in SYMBOLS]
    }
    ws.send(json.dumps(params))
    logging.info(f"Subscribed to WS: {params['args']}")

def run_websocket():
    ws_url = "wss://stream.bybit.com/realtime_public"
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

def periodic_fetch():
    while True:
        for symbol in SYMBOLS:
            fr = get_funding_rate(symbol)
            oi = get_open_interest(symbol)
            if fr is not None and oi is not None:
                logging.info(f"{symbol} Funding Rate: {fr}, Open Interest: {oi}")
            time.sleep(1)
        time.sleep(60)

if __name__ == "__main__":
    logging.info("Bot started")
    # Запускаем в потоках WebSocket и периодический опрос API
    threading.Thread(target=run_websocket, daemon=True).start()
    periodic_fetch()
