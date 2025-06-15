import pandas as pd
import ta

def analyze_signal(df: pd.DataFrame, cvd: float = 0, oi_delta: float = 0) -> dict:
    """
    Анализирует сигналы на вход и выход в LONG и SHORT на основе индикаторов:
    RSI, CCI, MACD Histogram, Bollinger Bands, CVD и Open Interest delta.

    Параметры:
        df: DataFrame с историей свечей
        cvd: float — текущее значение CVD (кумулятивная дельта)
        oi_delta: float — изменение OI за 3 свечи (положительное или отрицательное)

    Возвращает словарь с флагами сигналов и подробностями.
    """
    close = df['close']
    high = df['high']
    low = df['low']

    # Индикаторы
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    cci = ta.trend.CCIIndicator(high, low, close, window=20).cci()
    macd_hist = ta.trend.MACD(close).macd_diff()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)

    # Текущие значения
    rsi_curr = rsi.iloc[-1]
    cci_curr = cci.iloc[-1]
    macd_hist_curr = macd_hist.iloc[-1]
    macd_trend_up = macd_hist.iloc[-3:].is_monotonic_increasing
    macd_trend_down = macd_hist.iloc[-3:].is_monotonic_decreasing
    close_curr = close.iloc[-1]
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]

    # CVD/ OI усилители
    cvd_positive = cvd > 0
    cvd_negative = cvd < 0
    oi_rising = oi_delta > 0
    oi_falling = oi_delta < 0

    # Логика входа и выхода
    long_entry = (
        rsi_curr < 30 and
        cci_curr < -100 and
        macd_trend_up and
        close_curr <= bb_lower and
        cvd_positive and
        oi_rising
    )

    long_exit = (
        rsi_curr > 70 and
        cci_curr > 100 and
        macd_trend_down and
        close_curr >= bb_upper
    )

    short_entry = (
        rsi_curr > 70 and
        cci_curr > 100 and
        macd_trend_down and
        close_curr >= bb_upper and
        cvd_negative and
        oi_rising
    )

    short_exit = (
        rsi_curr < 30 and
        cci_curr < -100 and
        macd_trend_up and
        close_curr <= bb_lower
    )

    return {
        'long_entry': long_entry,
        'long_exit': long_exit,
        'short_entry': short_entry,
        'short_exit': short_exit,
        'details': {
            'rsi': rsi_curr,
            'cci': cci_curr,
            'macd_hist': macd_hist_curr,
            'close': close_curr,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'cvd': cvd,
            'oi_delta': oi_delta
        }
    }
