import os
import sys
import traceback
import logging
from datetime import datetime
import json

from fastapi import FastAPI, Request
from dotenv import load_dotenv

from bot import telegram_app, send_message
from scheduler import start_scheduler
from bybit_client import BybitClient  # для получения текущей цены

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

app = FastAPI()

async def get_tickers_and_prices():
    client = BybitClient()
    tickers = []
    try:
        with open("tickers.json", "r", encoding="utf-8") as f:
            tickers = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения tickers.json: {e}")
        return "Не удалось загрузить тикеры."

    messages = []
    for ticker in tickers:
        try:
            price = await client.get_current_price(ticker)
            messages.append(f"{ticker}: {price:.4f}")
        except Exception as e:
            logger.error(f"Ошибка получения цены для {ticker}: {e}")
            messages.append(f"{ticker}: цена недоступна")

    return "\n".join(messages)

@app.on_event("startup")
async def on_startup():
    try:
        tickers_prices = await get_tickers_and_prices()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        welcome_msg = (
            f"🚀 Бот запущен в {now} UTC.\n"
            f"Отслеживаемые тикеры и текущие цены:\n{tickers_prices}\n"
            f"Первый анализ будет через 15 минут."
        )
        await send_message(welcome_msg)
        logger.info("Startup message sent")

        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    try:
        update = await req.json()
        await telegram_app.update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
