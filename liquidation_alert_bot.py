import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = 'ВАШ_ТОКЕН_ТЕЛЕГРАМ'
OPEN_INTEREST_URL = "https://api.bybit.com/v5/market/open-interest"

# Мониторим эти символы
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AAVEUSDT"]

# Порог для уведомления (пример, можно менять)
OPEN_INTEREST_THRESHOLD = 0.03  # 3% от дневного объёма (пример)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Словарь для хранения дневного объема (будем обновлять раз в сутки)
daily_open_interest = {}

async def fetch_open_interest(session, symbol):
    try:
        params = {
            "category": "linear",
            "symbol": symbol,
            "intervalTime": "60",  # ВАЖНО: именно так, строчными буквами
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
        # Инициализация дневного объема, если нет
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
                logging.info(f"Symbol: {symbol}, base OI: {base_oi}, current OI: {current_oi}, change: {change:.4f}")

                if change > OPEN_INTEREST_THRESHOLD:
                    msg = (f"⚠️ Open Interest for {symbol} changed by {change*100:.2f}%!\n"
                           f"Base: {base_oi}\nCurrent: {current_oi}")
                    await bot.send_message(chat_id, msg)
                    # Обновляем базу после уведомления
                    daily_open_interest[symbol] = current_oi

            await asyncio.sleep(60)  # Проверяем каждую минуту

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я бот для отслеживания Open Interest на Bybit.\n"
                         "Я буду присылать уведомления, если объем изменится более чем на 3% за час.")
    # Запускаем задачу мониторинга
    asyncio.create_task(check_open_interest_changes(message.chat.id))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
