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

from bot import send_message       # твоя async функция отправки сообщений в телегу
from signals import analyze_signal # твоя функция анализа сигналов

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'
BASE_URL = "https://api.bybit.com/v5/market/kline"
OI_URL = "https://api.bybit.com/v5/market/open-interest"

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
    url = f"{OI_URL}?category=linear&symbol={ticker}&interval={TIMEFRAME}"
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

    # Запускаем задачу ровно по часам каждые 15 минут: 00, 15, 30, 45
    scheduler.add_job(run_async_job, trigger=CronTrigger(minute='0,15,30,45'))
    scheduler.start()
    logger.info("Scheduler started: every 15 minutes on the dot")

@app.on_event("startup")
async def on_startup():
    try:
        start_scheduler()

        # При старте сразу отправить приветственное сообщение с текущей ценой тикеров
        tickers = load_tickers()
        messages = []
        async with httpx.AsyncClient() as client:
            for ticker in tickers:
                resp = await client.get(BASE_URL, params={
                    'category': 'linear',
                    'symbol': ticker,
                    'interval': TIMEFRAME,
                    'limit': 1
                })
                resp.raise_for_status()
                data = resp.json()
                close_price = float(data['result']['list'][0]['close']) if data.get('retCode', 1) == 0 else None
                messages.append(f"🔔 <b>{ticker}</b> стартовая цена: {close_price:.4f}" if close_price else f"❗ {ticker} — цена недоступна")
        await send_message("🚀 Бот запущен.\n" + "\n".join(messages))

        logger.info("Startup complete, bot running.")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

@app.get("/")
async def root():
    return {"message": "Bot is running"}
