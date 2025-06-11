import asyncio
import logging
import os
import time
import aiohttp

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Переменные окружения
API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание экземпляров бота и диспетчера
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

# Хранилище последних значений open interest
latest_open_interest = {}

async def fetch_open_interest(session, symbol):
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&interval=1h"
    async with session.get(url) as response:
        data = await response.json()
        try:
            oi = float(data["result"]["list"][0]["openInterest"])
            return oi
        except Exception as e:
            logger.error(f"Ошибка при получении OI для {symbol}: {e}")
            return None

async def monitor_open_interest():
    symbols = ["BTCUSDT", "ETHUSDT", "AAVEUSDT", "SOLUSDT", "XMRUSDT"]
    interval = 300  # 5 минут

    async with aiohttp.ClientSession() as session:
        while True:
            for symbol in symbols:
                oi = await fetch_open_interest(session, symbol)
                if oi is None:
                    continue

                if symbol in latest_open_interest:
                    prev = latest_open_interest[symbol]
                    change_percent = abs(oi - prev) / prev * 100

                    if change_percent >= 3:
                        message = f"⚠️ Open Interest по <b>{symbol}</b> изменился на <b>{change_percent:.2f}%</b> за час.\nБыло: <code>{prev}</code>\nСтало: <code>{oi}</code>"
                        try:
                            await bot.send_message(CHAT_ID, message)
                        except Exception as e:
                            logger.error(f"Ошибка отправки сообщения: {e}")

                latest_open_interest[symbol] = oi

            await asyncio.sleep(interval)

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("Бот для отслеживания Open Interest запущен.")

# Подключаем router
dp.include_router(router)

async def main():
    asyncio.create_task(monitor_open_interest())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
