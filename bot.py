import json
import asyncio
from pybit import HTTP
from aiogram import Bot

# Инициализация Telegram бота (вставь свой токен)
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = YOUR_TELEGRAM_CHAT_ID  # Чат куда отправлять сообщения

telegram_bot = Bot(token=TELEGRAM_TOKEN)

# Очередь для входящих данных webhook
update_queue = asyncio.Queue()

# Инициализация клиента Bybit
bybit_client = HTTP(endpoint="https://api.bybit.com")

async def send_message(text: str):
    await telegram_bot.send_message(chat_id=CHAT_ID, text=text)

async def send_start_message():
    with open("tickers.json", "r") as f:
        tickers = json.load(f)

    messages = []
    for ticker in tickers:
        try:
            resp = bybit_client.latest_information_for_symbol(symbol=ticker)
            price = resp['result'][0]['last_price']
            messages.append(f"{ticker}: {price}")
        except Exception as e:
            messages.append(f"{ticker}: ошибка получения цены")

    text = "Бот запущен. Отслеживаемые тикеры и текущие цены:\n" + "\n".join(messages)
    await send_message(text)

async def process_updates():
    while True:
        update = await update_queue.get()
        # Тут обработка update, например сигналов и команд
        # Для простоты пропустим реализацию сейчас
        update_queue.task_done()
