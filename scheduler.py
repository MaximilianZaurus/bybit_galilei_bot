import asyncio
import json
import logging
import pandas as pd
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from bot import send_message       # асинхронная функция отправки сообщения в Telegram
from signals import analyze_signal # функция анализа сигналов

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'
BASE_URL = "https://api.bybit.com/v5/market/kline"
OI_URL_TEMPLATE = "https://api.bybit.com/v5/market/open-interest?category=linear&symbol={}&interval=15"

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
    url = OI_URL_TEMPLATE.format(ticker)
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
    # Заглушка, замени реальным CVD из трейдов
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

            signals = analyze_signal(df, cvd=cvd_value, oi_delta=oi_delta)
            d = signals.get('details', {})

            msg = (
                f"📊 <b>{ticker}</b>\n"
                f"Цена: {d.get('close', 0):.4f} | RSI: {d.get('rsi', 0):.1f} | MACD: {d.get('macd_hist', 0):.3f}\n"
                f"CVD: {cvd_value:.1f} | ΔOI: {oi_delta:.1f}\n"
                f"🟢 Лонг: {'✅' if signals.get('long_entry') else '—'}\n"
                f"🔴 Шорт: {'✅' if signals.get('short_entry') else '—'}"
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

    # Можно напрямую назначить async функцию
    scheduler.add_job(analyze_and_send, trigger=CronTrigger(minute='0,15,30,45'))
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

@app.get("/")
async def root():
    return {"message": "Bot is running"}
