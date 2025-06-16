from datetime import datetime
import pandas as pd

def get_klines(session, symbol, interval='15m', total_limit=2000):
    max_limit = 1000
    interval_map = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900,
        '30m': 1800, '1h': 3600, '2h': 7200,
        '4h': 14400, '1d': 86400
    }

    if interval not in interval_map:
        raise ValueError(f"Неподдерживаемый интервал: {interval}")

    if interval.endswith('m'):
        interval_api = interval[:-1]
    elif interval.endswith('h'):
        interval_api = str(int(interval[:-1]) * 60)
    elif interval.endswith('d'):
        interval_api = str(int(interval[:-1]) * 1440)
    else:
        interval_api = interval

    result = []
    end_time = int(datetime.utcnow().timestamp())
    count = 0

    while count < total_limit:
        limit = min(max_limit, total_limit - count)
        res = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval_api,
            limit=limit,
            end=end_time * 1000
        )
        if res.get('retCode', 1) != 0:
            raise Exception(f"Ошибка API get_kline: {res.get('retMsg')}")

        klines = res['result']['list']
        if not klines:
            break

        result = klines + result
        count += len(klines)

        oldest_time = int(klines[-1][0]) // 1000
        end_time = oldest_time - interval_map[interval]

    df = pd.DataFrame(result, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    return df.sort_values('open_time').reset_index(drop=True)


def load_tickers():
    # Возвращай нужный список тикеров
    return ['BTCUSDT', 'ETHUSDT']


def analyze_week(ticker):
    """
    Пример простой логики анализа.
    - Берем последние 100 свечей по 1д (день)
    - Считаем среднее закрытие
    - Возвращаем строку с результатом анализа
    """
    from pybit import usdt_perpetual  # Импорт клиента здесь, чтобы не на глобальном уровне

    session = usdt_perpetual.HTTP(endpoint="https://api.bybit.com")

    df = get_klines(session, ticker, interval='1d', total_limit=100)

    avg_close = df['close'].mean()

    result = f"{ticker} — среднее закрытие за 100 дней: {avg_close:.2f}"

    print(result)
    return result
