import pandas as pd
from datetime import datetime, timedelta

# Предполагается, что analyze_signal импортирована из signals.py
from signals import analyze_signal

class BybitClient:
    # ... ваш существующий код ...

    async def get_klines(self, symbol: str, timeframe: str, limit: int = 10) -> pd.DataFrame:
        """
        Получить исторические свечи OHLCV для символа с pybit HTTP.
        timeframe: "15m", "1h" и т.п. (используем маппинг TIMEFRAMES)
        """
        tf = TIMEFRAMES.get(timeframe)
        if tf is None:
            raise ValueError(f"Неподдерживаемый таймфрейм {timeframe}")

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self.http.get_kline(
                symbol=symbol,
                interval=tf,
                limit=limit,
                category=self.category
            )
        )
        if not resp or 'result' not in resp or not resp['result']:
            raise ValueError(f"Пустой ответ на get_kline для {symbol}")

        data = resp['result']

        df = pd.DataFrame(data)
        # Приводим к нужному типу
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        # Сортируем по времени по возрастанию
        df = df.sort_values('start').reset_index(drop=True)

        return df

    async def analyze_symbol(self, symbol: str, timeframe: str = "15m") -> dict:
        """
        Основная функция для анализа сигнала по символу:
        - Получает свечи
        - Берет cvd и oi_delta
        - Вызывает analyze_signal и возвращает результат
        """
        # Получаем свечи (например, 10 последних)
        df = await self.get_klines(symbol, timeframe, limit=10)

        # Текущее cvd и предыдущий (берём из self.CVD, можно передавать прошлое значение)
        current_cvd = self.CVD.get(symbol, 0.0)
        # Для prev_cvd можно взять из файла или предыдущее значение, упростим пока 0.0
        prev_cvd = 0.0  # или self.get_prev_cvd(symbol)

        # Получаем дельту OI
        oi_delta = self.get_oi_delta(symbol)

        # Цена предыдущего закрытия для анализа
        prev_close = df['close'].iloc[-2]

        # Вызываем функцию из signals.py
        signal_result = analyze_signal(df, current_cvd, oi_delta, prev_close=prev_close, prev_cvd=prev_cvd)

        return signal_result
