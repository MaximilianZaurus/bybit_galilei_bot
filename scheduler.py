from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from signals import check_galilei_signal, TICKERS
import asyncio

def setup_scheduler(bot: Bot, chat_id: str):
    scheduler = AsyncIOScheduler()

    scheduler.add_job(send_galilei_summary, "date", run_date=None, kwargs={
        "bot": bot, "chat_id": chat_id
    })

    scheduler.add_job(send_galilei_summary, "interval", hours=1, kwargs={
        "bot": bot, "chat_id": chat_id
    })

    scheduler.start()

async def send_galilei_summary(bot: Bot, chat_id: str):
    messages = []
    for ticker in TICKERS:
        try:
            signal, data = await check_galilei_signal(ticker)
            msg = f"📊 <b>{ticker}</b>\n"
            msg += f"1. Боллинджер: {'🟢' if data['close_psar'] <= data['psar'] else '❌'}\n"
            msg += f"2. CMO ({data['cmo']:.2f}): {'🟢' if data['cmo'] < -55 else '❌'}\n"
            msg += f"3. ADX ({data['adx']:.2f}): {'🟢' if data['adx'] > 35 else '❌'}\n"
            msg += f"4. PSAR ({data['psar']:.2f}): {'🟢' if data['psar'] < data['close_psar'] else '❌'}\n"
            msg += f"➡️ Сигнал: {'✅ Да' if signal else '❌ Нет'}\n"
            messages.append(msg)
        except Exception as e:
            messages.append(f"⚠️ Ошибка при анализе {ticker}: {e}")
    full_report = "\n\n".join(messages)
    await bot.send_message(chat_id=chat_id, text=full_report, parse_mode="HTML")
