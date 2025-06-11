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

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    logging.error("TELEGRAM_TOKEN и TELEGRAM_CHAT_ID должны быть заданы в переменных окружения")
    exit(1)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if not response.ok:
            logging.error(f"Telegram error: {response.text}")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

def fetch_funding_rate(symbol):
    url = f"https://api.bybit.com/v5/market/funding-rate?symbol={symbol}&category=linear"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Funding rate raw response for {symbol}: {json.dumps(data)}")
        if data.get("retCode") == 0:
            rates = data["result"].get("list", [])
            if rates:
                return float(rates[0]["fundingRate"])
        else:
            logging.error(f"Funding rate error {symbol}: {data.get('retMsg')}")
    except Exception as e:
        logging.error(f"Funding rate error {symbol}: {e}")
    return None

def fetch_open_interest(symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?symbol={symbol}&category=linear&interval=1h"
    try:
        response = requests.get(url)
        data = response.json()
        logging.info(f"Open interest raw response for {symbol}: {json.dumps(data)}")

        if data.get("retCode") != 0:
            logging.error(f"Open interest error {symbol}: {data.get('retMsg')}")
            return None

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

def on_message(ws, message):
    try:
        msg = json.loads(message)
        if "data" in msg:
            data = msg["data"]
            for item in data:
                symbol = item.get("symbol")
                if not symbol:
                    continue
                side = item.get("side")
                price = item.get("price")
                qty = item.get("size")
                ts = item.get("time")
                text = (f"🚨 <b>Liquidation Alert</b>\n"
                        f"Symbol: {symbol}\n"
                        f"Side: {side}\n"
                        f"Price: {price}\n"
                        f"Quantity: {qty}\n"
                        f"Timestamp: {ts}")
                send_telegram_message(text)
    except Exception as e:
        logging.error(f"Error in on_message: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.info("WebSocket connection closed")

def on_open(ws):
    logging.info(f"Subscribed to WS: {['liquidation.' + s for s in SYMBOLS]}")

def start_ws():
    ws_url = "wss://stream.bybit.com/realtime_public"
    params = {
        "op": "subscribe",
        "args": [f"liquidation.{symbol}" for symbol in SYMBOLS]
    }
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=lambda ws: ws.send(json.dumps(params)))
    ws.run_forever()

def main_loop():
    while True:
        for symbol in SYMBOLS:
            fr = fetch_funding_rate(symbol)
            oi_change = fetch_open_interest(symbol)

            msg = f"<b>{symbol}</b>\n"
            if fr is not None:
                msg += f"Funding Rate: {fr:.6f}\n"
            else:
                msg += "Funding Rate: no data\n"

            if oi_change is not None:
                msg += f"Open Interest Change 1h: {oi_change:.2f}%"
            else:
                msg += "Open Interest Change 1h: no data"

            logging.info(msg)
            time.sleep(1)
        time.sleep(30)

if __name__ == "__main__":
    logging.info("Bot started")

    # Запускаем WebSocket в отдельном потоке
    ws_thread = threading.Thread(target=start_ws)
    ws_thread.daemon = True
    ws_thread.start()

    main_loop()
