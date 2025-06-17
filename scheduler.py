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
        logger.info(f"Tickers loaded: {self.tickers} (type={type(self.tickers)})")

    def load_tickers(self):
        with open("tickers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise TypeError(f"Tickers.json должен содержать список, а получено: {type(data)}")
            return data

    async def start_ws_and_subscribe(self):
        logger.info(f"Подписка на тикеры: {self.tickers} (type={type(self.tickers)})")
        if not isinstance(self.tickers, list):
            raise TypeError(f"Ожидался список тикеров, а получено {type(self.tickers)}")
        self.client.subscribe_to_trades(self.tickers)
        await self.client.start_ws()

    async def fetch_and_analyze(self, timeframe: str):
        messages = []
        for ticker in self.tickers:
            try:
                klines = await self.client.get_klines(ticker, TIMEFRAMES[timeframe], limit=50)
                await self.client.update_oi_history(ticker)
                oi_delta = self.client.get_oi_delta(ticker)
                cvd_value = self.client.CVD.get(ticker, 0.0)
                prev_cvd = self.client.get_prev_cvd(ticker)

                signals = analyze_signal(klines, cvd=cvd_value, oi_delta=oi_delta)
                d = signals['details']

                price_change_percent = ((d['close'] - d['prev_close']) / d['prev_close']) * 100 if d['prev_close'] > 0 else 0
                price_up = d['close'] > d['prev_close']
                cvd_up = cvd_value > prev_cvd
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

                # Обновляем prev_cvd в клиенте
                self.client.update_prev_cvd(ticker, cvd_value)

            except Exception as e:
                logger.exception(f"Ошибка при обработке {ticker} {timeframe}: {e}")
                messages.append(f"❗ Ошибка с {ticker} ({timeframe}): {e}")

        final_message = "\n\n".join(messages)
        await send_message(final_message)

    def start(self):
        loop = asyncio.get_event_loop()

        # Запускаем WebSocket подписку как фоновую задачу
        loop.create_task(self.start_ws_and_subscribe())

        # Планируем задачи анализа
        self.scheduler.add_job(
            lambda: asyncio.create_task(self.fetch_and_analyze("15m")),
            trigger=CronTrigger(minute="0,15,30,45"),
            id="analyze_15m",
            replace_existing=True,
        )

        self.scheduler.add_job(
            lambda: asyncio.create_task(self.fetch_and_analyze("1h")),
            trigger=CronTrigger(minute="0"),
            id="analyze_1h",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started: 15m every 15 mins, 1h every hour")


def start_scheduler():
    scheduler = Scheduler()
    scheduler.start()
