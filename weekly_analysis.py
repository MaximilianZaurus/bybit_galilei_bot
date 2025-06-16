import json
from datetime import datetime, timedelta
import pandas as pd
import ta
from pybit.unified_trading import HTTP
import asyncio
import logging
import sys
import traceback
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot import send_message  # твоя асинхронная функция отправки сообщений в Telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEFRAME = '15'
session = HTTP(testnet=False)

app = FastAPI()

def load_tickers(path="tickers.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_klines(symbol, interval='15', limit=200):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API get_klines: {res['retMsg']}")

    raw_list = res['result']['list']
    if not raw_list or not isinstance(raw_list[0], list):
        raise Exception(f"Непредвиденный формат данных по {symbol}: {raw_list}")

    df = pd.DataFrame(raw_list, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'turnover', 'confirm', 'cross_seq', 'timestamp'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')

    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    return df.reset_index(drop=True)

def get_trades(symbol, start_time, end_time, limit=1000):
    res = session.get_public_trading_records(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Ошибка API trades: {res['retMsg']}")
    trades_df = pd.DataFrame(res['result']['list'])
    trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time'].astype(float), unit='ms')
    trades_df = trades_df[(trades_df['trade_time'] >= start_time) & (trades_df['trade_time'] < end_time)]
    for col in ['price', 'qty']:
        trades_df[col] = trades_df[col].astype(float)
    trades_df['isBuyerMaker'] = trades_df['isBuyerMaker'].astype(bool)
    return trades_df.reset_index(drop=True)

def calculate_cvd(trades_df):
    buy_volume = trades_df[~trades_df['isBuyerMaker']]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker']]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    if len(df) < window + 1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window - 1] if 'open_interest' in df else 0

def analyze_signal(df, cvd=0, oi_delta=0):
    close = df['close']
    high = df['high']
    low = df['low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd = ta.trend.MACD(close)
    macd_hist = macd.macd_diff().iloc[-1]
    macd_hist_prev = macd.macd_diff().iloc[-2]
    adx = ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1]

    long_entry = (
        (adx > 20) and
        (rsi < 35) and
        (macd_hist < 0 and macd_hist > macd_hist_prev) and
        (cvd > 0) and
        (oi_delta > 0)
    )
    long_exit = (
        (adx > 20) and
        (rsi > 60 or macd_hist < macd_hist_prev)
    )
    short_entry = (
        (adx > 20) and
        (rsi > 65) and
        (macd_hist > 0 and macd_hist < macd_hist_prev) and
        (cvd < 0) and
        (oi_delta < 0)
    )
    short_exit = (
        (adx > 20) and
        (rsi < 40 or macd_hist > macd_hist_prev)
    )

    return {
        'long_entry': long_entry,
        'long_exit': long_exit,
        'short_entry': short_entry,
        'short_exit': short_exit,
        'details': {
            'rsi': rsi,
            'macd_hist': macd_hist,
            'adx': adx,
            'close': close.iloc[-1],
            'cvd': cvd,
            'oi_delta': oi_delta
        }
    }

async def analyze_and_send():
    tickers = load_tickers()
    messages = []

    for ticker in tickers:
        try:
            df = get_klines(ticker, interval=TIMEFRAME)
            candle_time = df['open_time'].iloc[-1]
            start_trades = candle_time
            end_trades = candle_time + timedelta(minutes=15)
            trades = get_trades(ticker, start_trades, end_trades)
            cvd_value = calculate_cvd(trades)
            oi_delta = calculate_oi_delta(df)

            signals = analyze_signal(df, cvd=cvd_value, oi_delta=oi_delta)
            d = signals['details']

            msg = (
                f"📊 <b>{ticker}</b>\n"
                f"Цена: {d['close']:.4f} | RSI: {d['rsi']:.1f} | MACD: {d['macd_hist']:.3f} | ADX: {d['adx']:.1f}\n"
                f"CVD: {cvd_value:.1f} | ΔOI: {oi_delta:.1f}\n"
                f"🟢 Лонг: {'✅' if signals['long_entry'] else '—'}\n"
                f"🔴 Шорт: {'✅' if signals['short_entry'] else '—'}"
            )
            messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка при анализе {ticker}: {e}")
            messages.append(f"❌ Ошибка анализа {ticker}: {e}")

    final_message = "\n\n".join(messages)
    await send_message(final_message)

def analyze_week(symbol):
    now = datetime.utcnow()
    start = now - timedelta(days=7)
    df = get_klines(symbol, interval=TIMEFRAME, limit=2000)
    df = df[(df['open_time'] >= start) & (df['open_time'] < now)].reset_index(drop=True)

    long_entries = 0
    short_entries = 0

    for idx in range(200, len(df)):
        df_slice = df.iloc[idx - 200:idx + 1]
        candle_time = df_slice['open_time'].iloc[-1]
        trades = get_trades(symbol, candle_time, candle_time + timedelta(minutes=15))
        cvd = calculate_cvd(trades)
        oi_delta = calculate_oi_delta(df_slice)

        signals = analyze_signal(df_slice, cvd, oi_delta)
        if signals['long_entry']:
            long_entries += 1
        if signals['short_entry']:
            short_entries += 1

    print(f"{symbol} — за неделю: 🟢 Лонг: {long_entries}, 🔴 Шорт: {short_entries}")

scheduler = None

def start_scheduler():
    global scheduler
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(event_loop=loop)

    async def async_job_wrapper():
        await analyze_and_send()

    def run_async_job():
        asyncio.run_coroutine_threadsafe(async_job_wrapper(), loop)

    scheduler.add_job(run_async_job, trigger=CronTrigger(minute='0,15,30,45'))
    scheduler.start()
    logger.info("Scheduler запущен: анализ каждые 15 минут ровно")

@app.on_event("startup")
async def on_startup():
    try:
        start_scheduler()
        await send_message("🚀 Бот запущен. Первый анализ будет в ближайший 15-минутный интервал.")
        logger.info("Startup завершен, бот работает")
    except Exception as e:
        logger.error(f"Ошибка при старте: {e}")
        traceback.print_exc(file=sys.stdout)

@app.get("/")
async def root():
    return {"message": "Bot is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
