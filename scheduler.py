import asyncio
import json
import logging
from signal_analysis import BybitClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                return data.get("tickers", [])
        except Exception as e:
            logger.error(f"Ошибка загрузки тикеров: {e}")
            return []

    async def fetch_and_analyze(self, ticker: str, timeframe: str):
        try:
            signal_result = await self.client.analyze_symbol(ticker, timeframe)
            # Формируем сообщение с краткой информацией
            details = signal_result.get("details", {})
            comment = details.get("comment", "—")
            price_change = details.get("price_change_percent", 0)
            oi_delta = details.get("oi_delta", 0)
            cvd = details.get("cvd", 0)
            msg = (
                f"{ticker} [{timeframe}]: {comment}\n"
                f"Цена: {details.get('close', 0):.4f} ({price_change:+.2f}%)\n"
                f"OI Δ: {oi_delta:+.2f}, CVD: {cvd:+.2f}"
            )
            logger.info(msg)
            return msg
        except Exception as e:
            logger.error(f"Ошибка анализа {ticker} {timeframe}: {e}")
            return None

    async def run(self):
        # Запускаем WS и подписываемся
        await self.client.start_ws()
        self.client.subscribe_to_trades(self.tickers)

        # Основной цикл
        while True:
            for ticker in self.tickers:
                # Анализ 15m
                msg_15m = await self.fetch_and_analyze(ticker, "15m")
                # Анализ 1h
                msg_1h = await self.fetch_and_analyze(ticker, "1h")

                # Можно отправлять msg_15m и msg_1h в Telegram (вызовы API Telegram)

            await asyncio.sleep(900)  # 15 минут

if __name__ == "__main__":
    sched = Scheduler()
    asyncio.run(sched.run())
