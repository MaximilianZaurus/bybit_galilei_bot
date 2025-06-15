import asyncio
import json
import logging
import pandas as pd
import httpx
import sys
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from bot import send_message       # асинхронная функция отправки сообщения в Telegram
from signals import analyze_signal # функция анализа сигналов

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'  # 15-минутные свечи
BASE_URL = "https://api.bybit.com/v5/market/kline"

app = FastAPI()

def load_tickers():
    """Загружает тикеры из файла tickers.json"""
    with open('tickers.json', 'r', encoding='utf-8') as f:
        return json.load(f)

async def fetch_klines(ticker: str, limit=50) -> pd.DataFrame:
    """Асинхронно запрашивает свечные данные с Bybit и возвращает DataFrame"""
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

async def get_open_interest(ticker: str) -> float:
    """Получает текущий Open Interest с Bybit"""
    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={ticker}&interval=15"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            data = resp.json()
            return float(data['result']['list'][-1]['openInterest'])
    except Exception as e:
        logger.warning(f"Ошибка при получении OI для {ticker}: {e}")
        return None

def mock_cvd(df: pd.DataFrame) -> float:
    """Временный расчёт CVD — сумма дифференциала цены"""
    return df['close'].diff().fillna(0).cumsum().iloc[-1]

async def analyze_and_send():
    tickers = load_tickers()
    messages = []

    for ticker in tickers:
        try:
            df = await fetch_klines(ticker)
            signals = analyze_signal(df)

            cvd_value = mock_cvd(df)
            oi_value = await get_open_interest(ticker)

            d = signals['details']
            msg = (
                f"📈 <b>{ticker}</b>\n"
                f"Цена: {d['close']:.4f}\n"
                f"RSI: {d['rsi']:.2f} | CCI: {d['cci']:.2f} | MACD Hist: {d['macd_hist']:.4f}\n"
                f"Bollinger Bands: [{d['bb_lower']:.4f} - {d['bb_upper']:.4f}]\n"
                f"CVD: {cvd_value:.2f} | OI: {oi_value:.2f}\n\n"
                f"Сигналы:\n"
                f"▶️ Вход в Лонг: {'✅' if signals['long_entry'] else '❌'}\n"
                f"⏹ Выход из Лонга: {'✅' if signals['long_exit'] else '❌'}\n"
                f"▶️ Вход в Шорт: {'✅' if signals['short_entry'] else '❌'}\n"
                f"⏹ Выход из Шорта: {'✅' if signals['short_exit'] else '❌'}\n"
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

    scheduler.add_job(run_async_job, trigger=IntervalTrigger(minutes=15))
    scheduler.start()
    logger.info("Scheduler started, running every 15 minutes")

@app.on_event("startup")
async def on_startup():
    try:
        start_scheduler()
        await send_message("🚀 Бот запущен и работает. Первый анализ будет через 15 минут.")
        logger.info("Startup complete, bot running.")
    except Exception as e:
        logger.error(f"Error on startup: {e}")
        traceback.print_exc(file=sys.stdout)

@app.get("/")
async def root():
    return {"message": "Bot is running"}
