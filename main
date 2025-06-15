# main.py
import os
from fastapi import FastAPI, Request
from telegram import Update
from bot import application
from scheduler import start_scheduler

app = FastAPI()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

@app.on_event("startup")
async def startup():
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    start_scheduler()

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"status": "ok"}
