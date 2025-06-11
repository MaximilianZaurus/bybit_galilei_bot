import os
import json
import time
import logging
import requests
import websocket
import threading

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
WS_URL = "wss://stream.bybit.com/v5/public/linear"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if not response.ok:
            logging.error(f"Telegram error: {response.text}")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

def fetch_funding_rate(symbol):
    url = f"https://api.bybit.com/v5/market/funding/history?symbol={symbol}&category=linear"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Funding rate raw response for {symbol}: {json.dumps(data)}")
        if data["result"]["list"]:
            rate = float(data["result"]["list"][0]["fundingRate"]) * 100
            return rate
    except Exception as e:
        logging.error(f"Funding rate error {symbol}: {e}")
    return None

def fetch_open_interest(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?symbol={symbol}&category=linear&interval=1h"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Open interest raw response for {symbol}: {json.dumps(data)}")
        oi_list = data["result"].get("list", [])
        if len(oi_list) >= 2:
            oi_now = float(oi_list[0]["openInterest"])
            oi_prev = float(oi_list[1]["openInterest"])
            change_pct = ((oi_now - oi_prev) / oi_prev) * 100
            return change_pct
        else:
            logging.error(f"Open interest no data {symbol}: {data}")
    except Exception as e:
        logging.error(f"Open interest error {symbol}: {e}")
    return None

def monitor_metrics():
    while True:
        for symbol in SYMBOLS:
            funding_rate = fetch_funding_rate(symbol)
            open_interest_change = fetch_open_interest(symbol)
            messages = []

            if funding_rate is not None and abs(funding_rate) > 0.1:
                messages.append(f"⚠️ <b>{symbol}</b> funding rate: {funding_rate:.4f}%")

            if open_interest_change is not None and abs(open_interest_change) > 3:
                messages.append(f"📈 <b>{symbol}</b> OI change: {open_interest_change:.2f}%")

            for msg in messages:
                send_telegram_message(msg)

        time.sleep(300)  # 5 минут

def handle_liquidation_message(msg, symbol):
    try:
        if isinstance(msg, str):
            msg = json.loads(msg)

        data = msg.get("data", {})
        price = float(data.get("price", 0))
        quantity = float(data.get("qty", 0))
        side = data.get("side", "Unknown")

        if not price or not quantity:
            logging.warning(f"Incomplete liquidation data: {msg}")
            return

        value = price * quantity
        if value > 100_000:
            message = (
                f"💥 Ликвидация <b>{symbol}</b>\n"
                f"🔹 Side: {side}\n"
                f"🔹 Цена: {price}\n"
                f"🔹 Объём: {quantity}\n"
                f"🔹 Сумма: {int(value):,} USDT"
            )
            logging.info(f"Liquidation alert: {message}")
            send_telegram_message(message)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")

def on_message(ws, message):
    try:
        msg = json.loads(message)
        topic = msg.get("topic", "")
        for symbol in SYMBOLS:
            if topic == f"liquidation.{symbol}":
                handle_liquidation_message(msg, symbol)
    except Exception as e:
        logging.error(f"on_message error: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.warning(f"WebSocket closed: {close_status_code}, {close_msg}")

def on_open(ws):
    try:
        args = [f"liquidation.{symbol}" for symbol in SYMBOLS]
        payload = {
            "op": "subscribe",
            "args": args
        }
        ws.send(json.dumps(payload))
        logging.info(f"Subscribed to WS: {args}")
    except Exception as e:
        logging.error(f"WebSocket subscription error: {e}")

def run_ws():
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    logging.info("Bot started")
    t1 = threading.Thread(target=run_ws)
    t2 = threading.Thread(target=monitor_metrics)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
