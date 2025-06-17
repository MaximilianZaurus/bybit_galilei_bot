from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from signals import analyze_ticker
import json
import os
import datetime

bot = Bot(token=os.getenv("BOT_TOKEN"))
chat_id = os.getenv("CHAT_ID")

def run_analysis(interval: str):
    with open("tickers.json") as f:
        tickers = json.load(f)

    for ticker in tickers:
        try:
            msg = analyze_ticker(ticker, interval)
            bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            bot.send_message(chat_id=chat_id, text=f"Ошибка анализа {ticker}: {e}")

def schedule_jobs():
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(lambda: run_analysis("15"), "cron", minute="0,15,30,45")
    scheduler.add_job(lambda: run_analysis("60"), "cron", minute="0")

    scheduler.start()
