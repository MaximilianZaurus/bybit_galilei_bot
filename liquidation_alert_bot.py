import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiohttp import ClientSession

API_TOKEN = os.getenv("API_TOKEN")  # Токен берётся из переменных окружения
OPEN_INTEREST_URL = "https://api.bybit.com/v5/market/open-interest"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT", "XMRUSDT"]
OPEN_INTEREST_THRESHOLD = 0.03  # 3% изменения от базового значения

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# База OI
daily_open_interest = {}

async def fetch_open_interest(session: ClientSession, symbol: str) -> float | None:
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
                latest = data["result"]["list"][-1]
                return float(latest["openInterest"])
            else:
                logger.error(f"Ошибка в ответе Bybit по {symbol}: {data}")
    except Exception as e:
        logger.error(f"Ошибка при получении OI для {symbol}: {e}")
    return None

async def monitor_open_interest(chat_id: int):
    async with ClientSession() as session:
        for symbol in SYMBOLS:
            oi = await fetch_open_interest(session, symbol)
            if oi:
                daily_open_interest[symbol] = oi
                logger.info(f"Инициализация OI {symbol}: {oi}")

        while True:
            for symbol in SYMBOLS:
                current_oi = await fetch_open_interest(session, symbol)
                if current_oi is None:
                    continue
                base_oi = daily_open_interest.get(symbol, current_oi)
                change = abs(current_oi - base_oi) / base_oi
                if change > OPEN_INTEREST_THRESHOLD:
                    msg = (
                        f"⚠️ <b>Open Interest</b> изменился на <b>{change*100:.2f}%</b> по {symbol}\n"
                        f"Базовое значение: {base_oi:.2f}\n"
                        f"Текущее значение: {current_oi:.2f}"
                    )
                    await bot.send_message(chat_id=chat_id, text=msg)
                    daily_open_interest[symbol] = current_oi
            await asyncio.sleep(60)

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("🟢 Бот запущен. Мониторим Open Interest на Bybit.")
    asyncio.create_task(monitor_open_interest(message.chat.id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
