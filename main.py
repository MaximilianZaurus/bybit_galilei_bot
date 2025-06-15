import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from bot import telegram_app              # Объект Application от python-telegram-bot
from scheduler import start_scheduler     # Планировщик фоновых задач (analyze_and_send)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    start_scheduler()  # Запускаем планировщик при старте
    print("✅ Bot scheduler started")

@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    try:
        update = await req.json()
        await telegram_app.update(update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
