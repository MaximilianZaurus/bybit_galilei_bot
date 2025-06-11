import os
import json
import time
import threading
import requests
import logging
import websocket
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получение переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
WS_ENDPOINT = "wss://stream.bybit.com/v5/public/linear"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            logging.error(f"Telegram error: {response.text}")
    except Exception as e:
        logging.error(f"Telegram exception: {e}")

def fetch_funding_rate(symbol):
    url = f"https://api.bybit.com/v5/market/funding/history?symbol={symbol}&category=linear"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Funding rate raw response for {symbol}: {json.dumps(data)}")
        rate = data["result"]["list"][0]["fundingRate"]
        timestamp = int(data["result"]["list"][0]["fundingRateTimestamp"])
        dt = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        return f"📡 Funding Rate {symbol}: {rate}\n⏰ {dt}"
    except Exception as e:
        logging.error(f"Funding rate error {symbol}: {e}")
        return None

def fetch_open_interest(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?symbol={symbol}&category=linear&interval=5min"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Open interest raw response for {symbol}: {json.dumps(data)}")
        if not data["result"]["list"]:
            logging.error(f"Open interest no data {symbol}: {data}")
            return None
        latest = data["result"]["list"][-1]
        open_interest = latest["openInterest"]
        timestamp = int(latest["timestamp"])
        dt = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        return f"📊 Open Interest {symbol}: {open_interest}\n⏰ {dt}"
    except Exception as e:
        logging.error(f"Open interest error {symbol}: {e}")
        return None

def periodic_metrics():
    while True:
        for symbol in SYMBOLS:
            funding = fetch_funding_rate(symbol)
            oi = fetch_open_interest(symbol)
            if funding:
                send_telegram_message(funding)
            if oi:
                send_telegram_message(oi)
        time.sleep(300)  # каждые 5 минут

def on_message(ws, message):
    try:
        msg = json.loads(message)
        data = msg.get("data")
        if data:
            symbol = data.get("symbol")
            side = data.get("side")
            price = data.get("price")
            qty = data.get("qty")
            ts = datetime.fromtimestamp(data.get("ts") / 1000).strftime('%Y-%m-%d %H:%M:%S')

            if qty and float(qty) > 500000:
                alert = (
                    f"💥 Liquidation Alert\n"
                    f"🪙 Symbol: {symbol}\n"
                    f"📈 Side: {side}\n"
                    f"💰 Price: {price}\n"
                    f"📊 Quantity: {qty}\n"
                    f"🕓 Time: {ts}"
                )
                send_telegram_message(alert)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket general error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.warning("WebSocket closed, reconnecting...")
    time.sleep(5)
    run_websocket()

def on_open(ws):
    params = {
        "op": "subscribe",
        "args": [f"liquidation.{symbol}" for symbol in SYMBOLS]
    }
    ws.send(json.dumps(params))
    logging.info(f"Subscribed to WS: {[f'liquidation.{s}' for s in SYMBOLS]}")

def run_websocket():
    ws = websocket.WebSocketApp(
        WS_ENDPOINT,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    logging.info("Bot started")
    threading.Thread(target=periodic_metrics, daemon=True).start()
    run_websocket()
