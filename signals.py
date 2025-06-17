import pandas as pd

def analyze_signal(df: pd.DataFrame, cvd: float, oi_delta: float, prev_close: float = None, prev_cvd: float = 0.0) -> dict:
    """
    Анализ сигнала на основе цены закрытия, дельты открытого интереса (OI) и накопленной дельты объема (CVD).

    Args:
        df (pd.DataFrame): DataFrame с барами, должен содержать столбец 'close' и минимум 2 строки.
        cvd (float): Текущее значение CVD (накопленная дельта объема).
        oi_delta (float): Дельта открытого интереса (текущее OI минус OI 4 периода назад).
        prev_close (float, optional): Цена закрытия предыдущего периода. Если None, берется из df.
        prev_cvd (float, optional): Значение CVD предыдущего периода.

    Returns:
        dict: {'signal': str, 'details': dict} с сигналом и дополнительной информацией.
    """
    if df.shape[0] < 2:
        raise ValueError("DataFrame должен содержать минимум 2 строки для анализа")

    close = df['close'].iloc[-1]

    if prev_close is None:
        prev_close = df['close'].iloc[-2]

    price_change_percent = ((close - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0

    price_up = close > prev_close
    cvd_up = cvd > prev_cvd
    oi_up = oi_delta > 0

    if price_up and oi_up and cvd_up:
        comment = "💪 Сильный лонг"
    elif (not price_up) and oi_up and (not cvd_up):
        comment = "💪 Сильный шорт"
    else:
        comment = "—"

    details = {
        'close': close,
        'prev_close': prev_close,
        'price_change_percent': price_change_percent,
        'oi_delta': oi_delta,
        'cvd': cvd,
        'prev_cvd': prev_cvd,
        'comment': comment
    }

    return {
        'signal': comment,
        'details': details
    }
