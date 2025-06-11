import asyncio
import json
import logging
import requests
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]

FUNDING_RATE_URL = "https://api.bybit.com/public/linear/funding/prev-funding-rate"
OPEN_INTEREST_URL = "https://api.bybit.com/public/linear/open-interest"
WS_URL = "wss://stream.bybit.com/realtime_public"


def get_funding_rate(symbol):
    try:
        params = {"symbol": symbol}
        resp = requests.get(FUNDING_RATE_URL, params=params)
        logging.info(f"Funding rate HTTP status for {symbol}: {resp.status_code}")
        if resp.status_code != 200:
            logging.error(f"Funding rate response for {symbol}: {resp.text}")
            return None
        data = resp.json()
        if data.get("ret_code") == 0:
            rate = float(data["result"]["prev_funding_rate"])
            logging.info(f"Funding rate for {symbol}: {rate}")
            return rate
        else:
            logging.error(f"Funding rate error for {symbol}: {data.get('ret_msg')}")
    except Exception as e:
        logging.error(f"Funding rate exception for {symbol}: {e}")
    return None


def get_open_interest(symbol):
    try:
        params = {"symbol": symbol}
        resp = requests.get(OPEN_INTEREST_URL, params=params)
        logging.info(f"Open interest HTTP status for {symbol}: {resp.status_code}")
        if resp.status_code != 200:
            logging.error(f"Open interest response for {symbol}: {resp.text}")
            return None
        data = resp.json()
        if data.get("ret_code") == 0:
            oi = float(data["result"]["open_interest"])
            logging.info(f"Open interest for {symbol}: {oi}")
            return oi
        else:
            logging.error(f"Open interest error for {symbol}: {data.get('ret_msg')}")
    except Exception as e:
        logging.error(f"Open interest exception for {symbol}: {e}")
    return None


async def listen_liquidations():
    async with websockets.connect(WS_URL) as ws:
        # Подписка на ликвидации по символам
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"liquidation.{sym}" for sym in SYMBOLS]
        }
        await ws.send(json.dumps(subscribe_msg))
        logging.info(f"Subscribed to liquidation channels for: {', '.join(SYMBOLS)}")

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                # Проверяем, есть ли данные по ликвидациям
                if "data" in data and "topic" in data:
                    if data["topic"].startswith("liquidation."):
                        logging.info(f"Liquidation data: {data['data']}")
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
                break


async def main():
    logging.info("Bot started")

    # Получаем и логируем funding rate и open interest для всех символов
    for symbol in SYMBOLS:
        get_funding_rate(symbol)
        get_open_interest(symbol)

    # Запускаем WebSocket слушатель ликвидаций
    await listen_liquidations()


if __name__ == "__main__":
    asyncio.run(main())
