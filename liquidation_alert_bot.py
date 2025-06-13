import logging
import os
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.webhook.base import BaseRequestHandler
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.markdown import hbold

from fastapi import FastAPI, Request
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === Константы === #
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://bybit-liquidations.onrender.com").rstrip("/")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "AAVEUSDT", "SOLUSDT", "XMRUSDT", "TONUSDT", "NEARUSDT", "LTCUSDT", "APTUSDT", "WLDUSDT"]

# === Логгер === #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("liquidation_alert_bot")

# === Инициализация === #
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()
scheduler = AsyncIOScheduler()

# === Вспомогательные функции === #
async def fetch_bybit_data(symbol: str):
    url = f"https://api.bybit.com/v5/market/tickers?category=linear"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            for item in data.get("result", {}).get("list", []):
                if item["symbol"] == symbol:
                    return {
                        "symbol": symbol,
                        "lastPrice": float(item["lastPrice"]),
                        "volume24h": float(item["turnover24h"])
                    }
    return None

async def analyze_and_notify():
    logger.info("Анализ данных по парам...")
    messages = []
    for pair in TRADING_PAIRS:
        data = await fetch_bybit_data(pair)
        if data:
            price = data["lastPrice"]
            volume = data["volume24h"]
            logger.debug(f"{pair}: price={price}, volume24h={volume}")
            msg = f"<b>{pair}</b>\nЦена: {price:.2f}\nОбъём 24ч: {volume/1e6:.2f}M USDT"
            messages.append(msg)
        else:
            logger.warning(f"Нет данных по {pair}")
    if messages:
        summary = "📊 <b>Сводка по рынку:</b>\n\n" + "\n\n".join(messages)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=summary)

# === Обработчики Telegram === #
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.reply("Бот активен и работает. Ожидайте сигналов.")

@dp.message(F.text == "/debug")
async def cmd_debug(message: types.Message):
    await message.reply("🔧 Бот жив. Проверка логики в логах Render.")

@dp.message(F.text == "/summary")
async def cmd_summary(message: types.Message):
    await analyze_and_notify()

# === Webhook === #
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook установлен")
    scheduler.add_job(analyze_and_notify, "interval", hours=1, next_run_time=datetime.now() + timedelta(seconds=5))
    scheduler.start()

@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

@app.get("/")
async def root():
    return {"message": "Bot is running."}

@app.post("/")
async def fallback(request: Request):
    return {"status": "not a valid path"}
