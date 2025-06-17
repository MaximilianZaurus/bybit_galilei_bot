import pandas as pd

def analyze_signal(df: pd.DataFrame, cvd: float, oi_delta: float, prev_close: float = None, prev_cvd: float = 0.0) -> dict:
    """
    Анализ сигнала на основе закрытия цены, ΔOI и CVD.
    df - DataFrame с барами, обязательно содержит столбец 'close'
    cvd - текущее значение CVD (накопленная дельта изменения цены закрытия)
    oi_delta - дельта открытого интереса (текущий OI минус OI 4 периода назад)
    prev_close - цена закрытия предыдущего периода
    prev_cvd - значение CVD предыдущего периода
    """

    close = df['close'].iloc[-1]

    if prev_close is None:
        prev_close = df['close'].iloc[-2]

    price_change_percent = ((close - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0

    # Определяем тренды
    price_up = close > prev_close
    cvd_up = cvd > prev_cvd
    oi_up = oi_delta > 0

    # Логика сигналов
    if price_up and oi_up and cvd_up:
        comment = "💪 Сильный лонг"
    elif not price_up and oi_up and not cvd_up:
        comment = "💪 Сильный шорт"
    else:
        comment = "—"

    details = {
        'close': close,
        'prev_close': prev_close,
        'price_change_percent': price_change_percent,
        'oi_delta': oi_delta,
        'cvd': cvd,
        'comment': comment
    }

    return {
        'signal': comment,
        'details': details
    }
