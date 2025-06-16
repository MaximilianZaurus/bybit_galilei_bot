import os
import sys
import traceback
import logging
from datetime import datetime
import asyncio

from fastapi import FastAPI, Request
from dotenv import load_dotenv

from bot import telegram_app, send_message          # ✅ отправка сообщений
from scheduler import start_scheduler               # ✅ планировщик

from weekly_analysis import analyze_week            # ✅ анализ недели

# ✅ Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

# ✅ FastAPI
app = FastAPI()

# ✅ Асинхронный запуск недельного анализа
async def analyze_and_report():
    try:
        message = await asyncio.to_thread(analyze_week)  # Получаем результат анализа
        await send_message(message)                       # Отправляем в телегу полный отчет
        logger.info("Недельный анализ отправлен")
    except Exception as e:
        error_msg = f"❌ Ошибка при недельном анализе: {e}"
        logger.error(error_msg)
        await send_message(error_msg)

# ✅ Событие запуска FastAPI
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
        logger.error(f"Ошибка при запуске: {e}")
        traceback.print_exc(file=sys.stdout)

# ✅ Telegram Webhook
@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    try:
        update = await req.json()
        await telegram_app.update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# ✅ Корневой роут
@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
