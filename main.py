import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv

import logging
import sys
import traceback
from datetime import datetime

from bot import telegram_app              # Объект Application от python-telegram-bot
from scheduler import start_scheduler     # Планировщик фоновых задач (analyze_and_send)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    try:
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        await send_message(f"🚀 Бот запущен в {now} UTC. Первый анализ будет через 15 минут.")
        logger.info("Startup message sent")

        # Запускаем планировщик только после успешной отправки
        start_scheduler()

        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    try:
        update = await req.json()
        # В python-telegram-bot v20+ метод обработчика обновлений называется `process_update` или `update_queue.put` 
        # Но если telegram_app — ваш обёртка, оставляем await telegram_app.update(update)
        await telegram_app.update(update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
