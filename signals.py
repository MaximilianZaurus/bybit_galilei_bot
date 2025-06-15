import pandas as pd
import ta

def analyze_signal(df: pd.DataFrame) -> dict:
    """
    Анализ сигналов для входа/выхода из LONG и SHORT позиций.
    Используются RSI, CCI, MACD, Bollinger Bands, объём.

    Возвращает словарь с булевыми флагами и подробностями для дебага.
    """
    close = df['close']
    volume = df['volume']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    cci = ta.trend.CCIIndicator(df['high'], df['low'], close, window=20).cci()

    macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_hist = macd_ind.macd_diff()

    bb_ind = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_upper = bb_ind.bollinger_hband()
    bb_lower = bb_ind.bollinger_lband()

    volume_ma = volume.rolling(window=20).mean()

    rsi_curr = rsi.iloc[-1]
    cci_curr = cci.iloc[-1]
    macd_hist_curr = macd_hist.iloc[-1]
    close_curr = close.iloc[-1]
    bb_upper_curr = bb_upper.iloc[-1]
    bb_lower_curr = bb_lower.iloc[-1]
    volume_curr = volume.iloc[-1]
    volume_ma_curr = volume_ma.iloc[-1]

    macd_hist_trend = macd_hist.iloc[-3:].is_monotonic_increasing
    macd_hist_fall = macd_hist.iloc[-3:].is_monotonic_decreasing

    long_entry = (
        (rsi_curr < 30) and
        (cci_curr < -100) and
        macd_hist_trend and
        (close_curr <= bb_lower_curr) and
        (volume_curr > volume_ma_curr)
    )

    long_exit = (
        (rsi_curr > 70) and
        (cci_curr > 100) and
        macd_hist_fall and
        (close_curr >= bb_upper_curr)
    )

    short_entry = (
        (rsi_curr > 70) and
        (cci_curr > 100) and
        macd_hist_fall and
        (close_curr >= bb_upper_curr) and
        (volume_curr > volume_ma_curr)
    )

    short_exit = (
        (rsi_curr < 30) and
        (cci_curr < -100) and
        macd_hist_trend and
        (close_curr <= bb_lower_curr)
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
            'bb_upper': bb_upper_curr,
            'bb_lower': bb_lower_curr,
            'volume': volume_curr,
            'volume_ma': volume_ma_curr
        }
    }
