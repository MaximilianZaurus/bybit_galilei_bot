import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas as pd
from signals import TICKERS, fetch_klines, analyze_ticker
from bot import send_telegram_message

# Флаг волатильности по тикерам (True — высокая волатильность)
VOLATILITY_FLAGS = {ticker: False for ticker in TICKERS}

scheduler = AsyncIOScheduler()

def is_high_volatility(df: pd.DataFrame) -> bool:
    """Определяем высокую волатильность: изменение цены > 1.5% за последний интервал"""
    if len(df) < 2:
        return False
    prev_close = df['close'].iloc[-2]
    last_close = df['close'].iloc[-1]
    change = abs(last_close - prev_close) / prev_close
    return change > 0.015  # 1.5%

async def run_signal_analysis():
    for ticker in TICKERS:
        try:
            df = await fetch_klines(ticker, interval='15m', limit=50)
            high_volatility = is_high_volatility(df)
            VOLATILITY_FLAGS[ticker] = high_volatility

            message = await analyze_ticker(ticker, df)
            await send_telegram_message(message)
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    reschedule_job()

def reschedule_job():
    # Если по любому тикеру высокая волатильность — интервал 10 минут, иначе 30
    interval = 10 if any(VOLATILITY_FLAGS.values()) else 30
    scheduler.reschedule_job(
        "signal_analysis",
        trigger=IntervalTrigger(minutes=interval)
    )
    print(f"Scheduler interval updated to {interval} minutes.")

def start_scheduler(app, bot, CHAT_ID):
    scheduler.add_job(run_signal_analysis, IntervalTrigger(minutes=30), id="signal_analysis")
    scheduler.start()
    print("Scheduler started with 30-minute interval.")

    # При старте сразу запустим анализ (чтобы отправить стартовую статистику)
    asyncio.create_task(run_signal_analysis())
