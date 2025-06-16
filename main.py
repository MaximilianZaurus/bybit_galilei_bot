import os
import sys
import traceback
import logging
from datetime import datetime
import asyncio

from fastapi import FastAPI, Request
from dotenv import load_dotenv

from bot import telegram_app, send_message          # ✅ добавлен send_message
from scheduler import start_scheduler               # ✅ ваш планировщик

# Импорт функции для анализа и загрузки тикеров
from weekly_analysis import analyze_week, load_tickers

# ✅ Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Загрузка .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

# ✅ FastAPI app
app = FastAPI()

async def analyze_and_report():
    tickers = load_tickers()
    messages = []
    for ticker in tickers:
        try:
            # analyze_week — синхронная, запускаем в отдельном потоке
            await asyncio.to_thread(analyze_week, ticker)
            messages.append(f"✅ Анализ по {ticker} выполнен.")
        except Exception as e:
            messages.append(f"❌ Ошибка анализа {ticker}: {e}")
    report = "🚀 Стартовый анализ:\n" + "\n".join(messages)
    await send_message(report)

# ✅ Startup событие
@app.on_event("startup")
async def on_startup():
    try:
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        await send_message(f"🚀 Бот запущен в {now} UTC. Запускаем стартовый анализ.")
        logger.info("Startup message sent")

        await analyze_and_report()

        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

# ✅ Webhook для Telegram
@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    try:
        update = await req.json()
        await telegram_app.update(update)  # предполагается, что telegram_app реализует .update
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# ✅ Простой GET
@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
