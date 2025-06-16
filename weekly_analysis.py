def get_klines(symbol, interval='15m', total_limit=2000):
    """
    Получает до total_limit свечей по указанному символу и интервалу.
    Разбивает запрос на несколько сессий, т.к. лимит Bybit — 1000 свечей.
    """
    max_limit = 1000
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

    while count < total_limit:
        limit = min(max_limit, total_limit - count)
        res = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit,
            end=end_time * 1000  # в миллисекундах
        )

        if res.get('retCode') != 0:
            raise Exception(f"Ошибка API get_kline: {res.get('retMsg')}")

        klines = res['result']['list']
        if not klines:
            break

        # Добавить в начало, т.к. Bybit возвращает в порядке от новых к старым
        result = klines + result
        count += len(klines)

        # Обновляем конец запроса — смещаем назад по времени
        oldest_time = int(klines[-1][0]) // 1000  # ms → s
        end_time = oldest_time - interval_map[interval]

    # Преобразуем в DataFrame
    df = pd.DataFrame(result, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)

    return df.sort_values('open_time').reset_index(drop=True)
