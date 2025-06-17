import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bybit_client import BybitClient

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.client = BybitClient()
        self.scheduler = AsyncIOScheduler()
        self.tickers = []

    def load_tickers(self):
        # Здесь загружаются тикеры из файла или конфига
        import json
        with open("tickers.json", "r", encoding="utf-8") as f:
            self.tickers = json.load(f)
        logger.info(f"Tickers loaded: {self.tickers} (type={type(self.tickers)})")

    async def start_ws_and_subscribe(self):
        self.client.subscribe_to_trades(self.tickers)
        logger.info(f"Subscribed to tickers: {self.tickers}")

    def schedule_jobs(self):
        # Пример расписания
        self.scheduler.add_job(lambda: logger.info("Job 15m running"), "interval", minutes=15, id="job_15m")
        self.scheduler.add_job(lambda: logger.info("Job 1h running"), "interval", hours=1, id="job_1h")

    def start(self):
        self.load_tickers()
        asyncio.create_task(self.start_ws_and_subscribe())
        self.schedule_jobs()
        self.scheduler.start()
        logger.info("Scheduler started")

_scheduler_instance = None

def start_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = Scheduler()
    _scheduler_instance.start()
