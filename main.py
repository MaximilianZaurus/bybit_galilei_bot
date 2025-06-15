import os
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CallbackContext, ApplicationBuilder
from scheduler import setup_scheduler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

bot = Bot(token=TOKEN)
app = FastAPI()

application = ApplicationBuilder().token(TOKEN).build()
setup_scheduler(bot)

@app.post("/webhook")
async def webhook_handler(request: Request):
    update = Update.de_json(data=await request.json(), bot=bot)
    await application.process_update(update)
    return {"ok": True}
