import asyncio
import json
import logging
from signals import analyze_signal
from bybit_client import BybitClient  # твой клиент

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Scheduler:
    def __init__(self, tickers_file="tickers.json"):
        self.client = BybitClient()
        self.tickers_file = tickers_file
        self.tickers = self.load_tickers()

    def load_tickers(self):
        try:
            with open(self.tickers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Загружены тикеры: {data}")
                if isinstance(data, list):
                    return data
                else:
                    logger.error("Формат tickers.json неверный — ожидается список строк")
                    return []
        except Exception as e:
            logger.error(f"Ошибка загрузки тикеров: {e}")
            return []

    async def fetch_and_analyze(self, ticker: str, timeframe: str):
        try:
            result = await self.client.analyze_symbol(ticker, timeframe)
            details = result.get("details", {})
            comment = details.get("comment", "—")
            price_change = details.get("price_change_percent", 0.0)
            oi_delta = details.get("oi_delta", 0.0)
            cvd = details.get("cvd", 0.0)

            msg = (
                f"{ticker} [{timeframe}]: {comment}\n"
                f"Цена: {details.get('close', 0):.4f} ({price_change:+.2f}%)\n"
                f"OI Δ: {oi_delta:+.2f}, CVD: {cvd:+.2f}"
            )
            logger.info(msg)
            return msg
        except Exception as e:
            logger.error(f"Ошибка анализа {ticker} [{timeframe}]: {e}")
            return None

    async def run(self):
        logger.info(f"Тип self.tickers: {type(self.tickers)}, значение: {self.tickers}")
        await self.client.start_ws()

        if not isinstance(self.tickers, list):
            logger.error(f"tickers is not a list! Got: {self.tickers}")
            self.tickers = []

        self.client.subscribe_to_trades(self.tickers)

        while True:
            for ticker in self.tickers:
                await self.fetch_and_analyze(ticker, "15m")
                await self.fetch_and_analyze(ticker, "1h")

            await asyncio.sleep(900)  # 15 минут

async def start_scheduler():
    scheduler = Scheduler()
    await scheduler.run()
