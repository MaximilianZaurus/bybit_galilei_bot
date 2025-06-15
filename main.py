# main.py
import os
import asyncio
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from bot import telegram_app
from scheduler import start_scheduler

load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_scheduler())

@app.post(f"/webhook/{os.getenv('BOT_TOKEN')}")
async def telegram_webhook(req: Request):
    update = await req.json()
    await telegram_app.update(update)
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"status": "Galilei bot running"}
