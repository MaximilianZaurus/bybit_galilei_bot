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
            result, indicators = await check_galilei_signal(symbol)
            if result:
                msg = (
                    f"🟢 Сигнал по стратегии «Галилей» на {symbol}\n\n"
                    f"📈 *Индикаторы:*\n"
                    f"Bollinger Lower Touch (1h): ✅\n"
                    f"CMO (30m): {indicators['cmo']:.2f} (< -55 ✅)\n"
                    f"ADX (30m): {indicators['adx']:.2f} (> 35 ✅)\n"
                    f"Parabolic SAR (5m): {indicators['psar']:.2f} < Цена ({indicators['close_psar']:.2f}) ✅"
                )
                await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Ошибка на {symbol}: {e}")

def start_scheduler():
    scheduler.add_job(run_signal_checks, "interval", minutes=15)
    scheduler.start()
