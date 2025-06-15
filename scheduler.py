import asyncio
import json
import logging
import pandas as pd
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import send_message  # Асинхронная функция отправки сообщения в Telegram
from signals import analyze_signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'  # 15 минутные свечи
API_URL = 'https://api.bybit.com/public/linear/kline'


def load_tickers():
    """Загружает тикеры из файла tickers.json"""
    with open('tickers.json', 'r') as f:
        return json.load(f)


async def fetch_klines(ticker: str, limit=50) -> pd.DataFrame:
    """Асинхронно запрашивает свечные данные с Bybit и возвращает DataFrame"""
    params = {
        'symbol': ticker,
        'interval': TIMEFRAME,
        'limit': limit
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get('ret_code', 1) != 0:
        raise Exception(f"API Error for {ticker}: {data.get('ret_msg')}")

    klines = data['result']
    df = pd.DataFrame(klines)
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
    df['open_time'] = pd.to_datetime(df['open_time'], unit='s')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    return df


async def analyze_and_send():
    tickers = load_tickers()
    messages = []

    for ticker in tickers:
        try:
            df = await fetch_klines(ticker)
            signals = analyze_signal(df)
            d = signals['details']

            msg = (
                f"📈 <b>{ticker}</b>\n"
                f"Цена: {d['close']:.4f}\n"
                f"RSI: {d['rsi']:.2f} | CCI: {d['cci']:.2f} | MACD Hist: {d['macd_hist']:.4f}\n"
                f"Bollinger Bands: [{d['bb_lower']:.4f} - {d['bb_upper']:.4f}]\n"
                f"Объём: {d['volume']:.2f} (средний: {d['volume_ma']:.2f})\n\n"
                f"Сигналы:\n"
                f"▶️ Вход в Лонг: {'✅' if signals['long_entry'] else '❌'}\n"
                f"⏹ Выход из Лонга: {'✅' if signals['long_exit'] else '❌'}\n"
                f"▶️ Вход в Шорт: {'✅' if signals['short_entry'] else '❌'}\n"
                f"⏹ Выход из Шорта: {'✅' if signals['short_exit'] else '❌'}\n"
            )
            messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка при обработке {ticker}: {e}")
            messages.append(f"Ошибка с {ticker}: {e}")

    final_message = "\n\n".join(messages)
    await send_message(final_message)


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(analyze_and_send()), 'interval', minutes=15)
    scheduler.start()
    logger.info("Scheduler started, running every 15 minutes")
