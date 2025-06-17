from fastapi import FastAPI, Request
from bot import app as telegram_app
from scheduler import schedule_jobs

app = FastAPI()
schedule_jobs()

@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.json()
    await telegram_app.update_queue.put(body)
    return {"status": "ok"}
