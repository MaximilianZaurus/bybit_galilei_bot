import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from fastapi import FastAPI
import uvicorn
from threading import Thread
import os

API_TOKEN = os.getenv("API_TOKEN")
OPEN_INTEREST_URL = "https://api.bybit.com/v5/market/open-interest"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
OPEN_INTEREST_THRESHOLD = 0.03  # 3%
daily_open_interest = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# Telegram bot
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# FastAPI health check
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

async def fetch_open_interest(session, symbol):
    try:
        params = {
            "category": "linear",
            "symbol": symbol,
            "intervalTime": "60",
            "limit": 1
        }
        async with session.get(OPEN_INTEREST_URL, params=params) as response:
            data = await response.json()
            if data.get("retCode") == 0 and data["result"]["list"]:
                return float(data["result"]["list"][-1]["openInterest"])
    except Exception as e:
        logging.error(f"{symbol} error: {e}")
    return None

async def check_open_interest_changes(chat_id):
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            if symbol not in daily_open_interest:
                value = await fetch_open_interest(session, symbol)
                if value:
                    daily_open_interest[symbol] = value

        while True:
            for symbol in SYMBOLS:
                current = await fetch_open_interest(session, symbol)
                if current is None:
                    continue
                base = daily_open_interest.get(symbol, current)
                change = abs(current - base) / base
                if change > OPEN_INTEREST_THRESHOLD:
                    msg = (f"⚠️ Open Interest for {symbol} changed by {change*100:.2f}%!\n"
                           f"Base: {base}\nCurrent: {current}")
                    await bot.send_message(chat_id, msg)
                    daily_open_interest[symbol] = current
            await asyncio.sleep(60)

@dp.message(commands=["start"])
async def start_handler(message: Message):
    await message.answer("👋 Бот запущен! Буду следить за Open Interest.")
    asyncio.create_task(check_open_interest_changes(message.chat.id))

def run_bot():
    asyncio.run(dp.start_polling(bot))

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=10000)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    run_api()
