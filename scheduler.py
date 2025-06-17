import asyncio
import json
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bybit_client import BybitClient
from bot import send_message
from signals import analyze_signal

logger = logging.getLogger(__name__)

TIMEFRAMES = {
    "15m": "15",
    "1h": "60"
}

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.client = BybitClient()
        self.tickers = self.load_tickers()

    def load_tickers(self):
        with open("tickers.json", "r", encoding="utf-8") as f:
            return json.load(f)

    async def fetch_and_analyze(self, timeframe: str):
        messages = []
        for ticker in self.tickers:
            try:
                klines = await self.client.get_klines(ticker, TIMEFRAMES[timeframe], limit=50)
                oi_history = await self.client.get_open_interest_history(ticker, TIMEFRAMES[timeframe])
                oi_delta = self.calculate_oi_delta(oi_history)
                oi_value = float(oi_history[-1]['openInterest']) if oi_history else 0.0
                cvd_value = self.calculate_cvd(klines)

                signals = analyze_signal(klines, cvd=cvd_value, oi_delta=oi_delta)
                d = signals['details']

                price_change_percent = ((d['close'] - d['prev_close']) / d['prev_close']) * 100 if d['prev_close'] > 0 else 0

                comment = ""
                price_up = d['close'] > d['prev_close']
                cvd_up = cvd_value > signals.get('prev_cvd', 0)
                oi_up = oi_delta > 0

                if price_up and oi_up and cvd_up:
                    comment = "💪 Сильный лонг"
                elif not price_up and oi_up and not cvd_up:
                    comment = "💪 Сильный шорт"
                else:
                    comment = "—"

                msg = (
                    f"⏱ <b>{ticker} [{timeframe}]</b>\n"
                    f"Цена закрытия: {d['close']:.4f} ({price_change_percent:+.2f}%)\n"
                    f"ΔOI: {oi_delta:+.2f}\n"
                    f"CVD: {cvd_value:+.2f}\n"
                    f"{comment}"
                )
                messages.append(msg)
            except Exception as e:
                logger.error(f"Ошибка при обработке {ticker} {timeframe}: {e}")
                messages.append(f"❗ Ошибка с {ticker} ({timeframe}): {e}")

        final_message = "\n\n".join(messages)
        await send_message(final_message)

    @staticmethod
    def calculate_oi_delta(oi_list):
        if len(oi_list) < 4:
            return 0.0
        try:
            current = float(oi_list[-1]['openInterest'])
            past = float(oi_list[-4]['openInterest'])
            return current - past
        except Exception:
            return 0.0

    @staticmethod
    def calculate_cvd(klines):
        closes = [float(k['close']) for k in klines]
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        return sum(diffs)

    def start(self):
        loop = asyncio.get_event_loop()

        def schedule_job(coro):
            asyncio.run_coroutine_threadsafe(coro, loop)

        self.scheduler.add_job(
            lambda: schedule_job(self.fetch_and_analyze("15m")),
            trigger=CronTrigger(minute="0,15,30,45"),
            id="analyze_15m",
            replace_existing=True,
        )

        self.scheduler.add_job(
            lambda: schedule_job(self.fetch_and_analyze("1h")),
            trigger=CronTrigger(minute="0"),
            id="analyze_1h",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started: 15m every 15 mins, 1h every hour")


def start_scheduler():
    scheduler = Scheduler()
    scheduler.start()
