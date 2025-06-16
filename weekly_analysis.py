from datetime import datetime
import pandas as pd

def get_klines(session, symbol, interval='15m', total_limit=2000):
    """
    Получает до total_limit свечей по указанному символу и интервалу с Bybit (v5).
    Разбивает запрос на несколько сессий, т.к. лимит Bybit — 1000 свечей.
    
    Параметры:
    - session: экземпляр pybit v5 client
    - symbol: строка, например "BTCUSDT"
    - interval: строка, например "15m", "1h"
    - total_limit: макс. количество свечей
    
    Возвращает pd.DataFrame с колонками:
    ['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    """
    max_limit = 1000
    # Сопоставление интервалов в секунды для сдвига времени
    interval_map = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900,
        '30m': 1800, '1h': 3600, '2h': 7200,
        '4h': 14400, '1d': 86400
    }

    if interval not in interval_map:
        raise ValueError(f"Неподдерживаемый интервал: {interval}")

    result = []
    end_time = int(datetime.utcnow().timestamp())
    count = 0

    # В pybit v5 interval передаётся без 'm' и т.д., только число как строка
    interval_api = interval.replace('m', '')\
                           .replace('h', '60')\
                           .replace('d', '1440')
    # Лучше явнее:
    if interval.endswith('m'):
        interval_api = interval[:-1]
    elif interval.endswith('h'):
        interval_api = str(int(interval[:-1]) * 60)
    elif interval.endswith('d'):
        interval_api = str(int(interval[:-1]) * 1440)

    while count < total_limit:
        limit = min(max_limit, total_limit - count)
        res = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval_api,
            limit=limit,
            end= end_time * 1000  # в миллисекундах
        )

        if res.get('retCode', 1) != 0:
            raise Exception(f"Ошибка API get_kline: {res.get('retMsg')}")

        klines = res['result']['list']
        if not klines:
            break

        # Bybit возвращает свечи от новых к старым, складываем так, чтобы получить правильный порядок
        result = klines + result
        count += len(klines)

        oldest_time = int(klines[-1][0]) // 1000  # время в секундах
        end_time = oldest_time - interval_map[interval]

    df = pd.DataFrame(result, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    return df.sort_values('open_time').reset_index(drop=True)
