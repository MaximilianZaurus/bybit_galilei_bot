import asyncio
import json
import logging
import pandas as pd
import httpx
import sys
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from bot import send_message       # асинхронная функция отправки сообщения в Telegram
from signals import analyze_signal # функция анализа сигналов

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'
BASE_URL = "https://api.bybit.com/v5/market/kline"

app = FastAPI()

def load_tickers():
    with open('tickers.json', 'r', encoding='utf-8') as f:
        return json.load(f)

async def fetch_klines(ticker: str, limit=50) -> pd.DataFrame:
    params = {
        'category': 'linear',
        'symbol': ticker,
        'interval': TIMEFRAME,
        'limit': limit
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get('retCode', 1) != 0:
        raise Exception(f"API Error for {ticker}: {data.get('retMsg')}")

    klines = data.get('result', {}).get('list', [])
    if not klines:
        raise Exception(f"No kline data returned for {ticker}")

    df = pd.DataFrame(klines)
    df.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume'] + [f"extra_{i}" for i in range(len(df.columns) - 6)]
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    return df

async def get_open_interest_history(ticker: str) -> list[dict]:
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={ticker}&interval=15"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data.get('retCode', 1) != 0:
                raise Exception(f"API error: {data.get('retMsg')}")
            return data['result']['list']
    except Exception as e:
        logger.warning(f"Ошибка при получении истории OI для {ticker}: {e}")
        return []

def calculate_oi_delta(oi_list: list[dict]) -> float:
    if len(oi_list) < 4:
        return 0.0
    try:
        current = float(oi_list[-1]['openInterest'])
        past = float(oi_list[-4]['openInterest'])
        return current - past
    except Exception as e:
        logger.warning(f"Ошибка при расчёте oi_delta: {e}")
        return 0.0

def mock_cvd(df: pd.DataFrame) -> float:
    return df['close'].diff().fillna(0).cumsum().iloc[-1]

async def analyze_and_send():
    tickers = load_tickers()
    messages = []

    for ticker in tickers:
        try:
            df = await fetch_klines(ticker)
            cvd_value = mock_cvd(df)
            oi_history = await get_open_interest_history(ticker)
            oi_delta = calculate_oi_delta(oi_history)
            oi_value = float(oi_history[-1]['openInterest']) if oi_history else 0.0

            signals = analyze_signal(df, cvd=cvd_value, oi_delta=oi_delta)
            d = signals['details']

            msg = (
                f"📊 <b>{ticker}</b>\n"
                f"Цена: {d['close']:.4f} | RSI: {d['rsi']:.1f} | MACD: {d['macd_hist']:.3f}\n"
                f"BB: [{d['bb_lower']:.2f} - {d['bb_upper']:.2f}] | CVD: {cvd_value:.1f} | ΔOI: {oi_delta:.1f}\n"
                f"🟢 Лонг: {'✅' if signals['long_entry'] else '—'}\n"
                f"🔴 Шорт: {'✅' if signals['short_entry'] else '—'}"
            )
            messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка при обработке {ticker}: {e}")
            messages.append(f"❗ Ошибка с {ticker}: {e}")

    final_message = "\n\n".join(messages)
    await send_message(final_message)

scheduler = None

def start_scheduler():
    global scheduler
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(event_loop=loop)

    async def async_job_wrapper():
        await analyze_and_send()

    def run_async_job():
        asyncio.run_coroutine_threadsafe(async_job_wrapper(), loop)

    # Каждые 15 минут по часам: 00, 15, 30, 45
    scheduler.add_job(run_async_job, trigger=CronTrigger(minute='0,15,30,45'))
    scheduler.start()
    logger.info("Scheduler started with CronTrigger: every 15 mins on the dot")

@app.on_event("startup")
async def on_startup():
    try:
        start_scheduler()
        await send_message("🚀 Бот запущен. Первый анализ будет в ближайший 15-минутный интервал.")
        logger.info("Startup complete, bot running.")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

@app.get("/")
async def root():
    return {"message": "Bot is running"}
