from fastapi import FastAPI, Request
from bot import app as telegram_app, send_start_message, update_queue, process_updates
from scheduler import schedule_jobs
import asyncio

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await send_start_message()  # Отправляем стартовое сообщение при запуске
    schedule_jobs()             # Запускаем шедулер
    asyncio.create_task(process_updates())  # Фоновый обработчик очереди телеги

@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.json()
    await update_queue.put(body)
    return {"status": "ok"}
