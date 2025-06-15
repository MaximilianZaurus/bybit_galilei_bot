# scheduler.py
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot import application
from signals import check_galilei_signal, TICKERS

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
scheduler = AsyncIOScheduler()

async def run_signal_checks():
    for symbol in TICKERS:
        try:
            result = await check_galilei_signal(symbol)
            if result:
                msg = f"🟢 Сигнал по стратегии «Галилей» на {symbol}"
                await application.bot.send_message(chat_id=CHAT_ID, text=msg)
        except Exception as e:
            print(f"Ошибка на {symbol}: {e}")

def start_scheduler():
    scheduler.add_job(run_signal_checks, "interval", minutes=30)
    scheduler.start()
