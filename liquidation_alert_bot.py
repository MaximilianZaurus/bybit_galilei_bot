import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = 'ВАШ_ТОКЕН_ТЕЛЕГРАМ'
OPEN_INTEREST_URL = "https://api.bybit.com/v5/market/open-interest"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]
OPEN_INTEREST_THRESHOLD = 0.03  # 3%

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

daily_open_interest = {}

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
            logging.info(f"Open interest raw response for {symbol}: {data}")
            if data.get("retCode") == 0 and data["result"]["list"]:
                latest = data["result"]["list"][-1]
                value = float(latest["openInterest"])
                return value
            else:
                logging.error(f"Open interest response error for {symbol}: {data}")
    except Exception as e:
        logging.error(f"Open interest error {symbol}: {e}")
    return None

async def check_open_interest_changes(chat_id):
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            if symbol not in daily_open_interest:
                oi = await fetch_open_interest(session, symbol)
                if oi:
                    daily_open_interest[symbol] = oi
                    logging.info(f"Set daily open interest for {symbol}: {oi}")

        while True:
            for symbol in SYMBOLS:
                current_oi = await fetch_open_interest(session, symbol)
                if current_oi is None:
                    continue
                base_oi = daily_open_interest.get(symbol, current_oi)
                change = abs(current_oi - base_oi) / base_oi
                logging.info(f"{symbol}: base {base_oi}, current {current_oi}, change {change:.2%}")

                if change > OPEN_INTEREST_THRESHOLD:
                    msg = (f"⚠️ Open Interest for <b>{symbol}</b> changed by <b>{change*100:.2f}%</b>!\n"
                           f"Base: {base_oi:.2f}\nCurrent: {current_oi:.2f}")
                    await bot.send_message(chat_id, msg)
                    daily_open_interest[symbol] = current_oi

            await asyncio.sleep(60)

@dp.message()
async def handle_start(message: Message):
    if message.text == "/start":
        await message.answer("Привет! Я бот для отслеживания Open Interest на Bybit.")
        asyncio.create_task(check_open_interest_changes(message.chat.id))

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
