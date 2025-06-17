import os
import json
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bybit_client import BybitClient

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.client = BybitClient()
        self.tickers = self.load_tickers()
        logger.info(f"Tickers loaded: {self.tickers} (type={type(self.tickers)})")

    def load_tickers(self):
        try:
            with open("tickers.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise TypeError(f"tickers.json должен содержать список, а получено: {type(data)}")
                return data
        except FileNotFoundError:
            logger.error("Файл tickers.json не найден.")
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки tickers.json: {e}")
            return []

    async def safe_start_ws_and_subscribe(self):
        try:
            await self.start_ws_and_subscribe()
        except Exception as e:
            logger.error(f"Ошибка в start_ws_and_subscribe: {e}")

    async def start_ws_and_subscribe(self):
        logger.info(f"Подписка на тикеры: {self.tickers} (type={type(self.tickers)})")
        if not isinstance(self.tickers, list):
            raise TypeError(f"Ожидался список тикеров, а получено {type(self.tickers)}")

        await self.client.start_ws()
        # subscribe_to_trades — синхронный метод, вызываем без await
        self.client.subscribe_to_trades(self.tickers)
        logger.info("Подписка на WebSocket выполнена")

    async def safe_fetch_and_analyze(self, timeframe):
        try:
            await self.fetch_and_analyze(timeframe)
        except Exception as e:
            logger.error(f"Ошибка в fetch_and_analyze ({timeframe}): {e}")

    async def fetch_and_analyze(self, timeframe):
        logger.info(f"Запуск анализа по таймфрейму {timeframe}")
        # Здесь вызывай нужные методы анализа, например:
        # await self.client.fetch_candles_and_analyze(timeframe, self.tickers)
        # Твой код анализа...

    def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.safe_start_ws_and_subscribe())

        self.scheduler.add_job(
            lambda: asyncio.create_task(self.safe_fetch_and_analyze("15m")),
            trigger=CronTrigger(minute="0,15,30,45"),
            id="analyze_15m",
            replace_existing=True,
        )

        self.scheduler.add_job(
            lambda: asyncio.create_task(self.safe_fetch_and_analyze("1h")),
            trigger=CronTrigger(minute="0"),
            id="analyze_1h",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started: 15m every 15 mins, 1h every hour")
