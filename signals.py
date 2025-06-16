import pandas as pd
import ta

def analyze_signal(df: pd.DataFrame, cvd: float = 0, oi_delta: float = 0) -> dict:
    close = df['close']
    high = df['high']
    low = df['low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    cci = ta.trend.CCIIndicator(high, low, close, window=20).cci()
    macd_hist = ta.trend.MACD(close).macd_diff()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)

    rsi_curr = rsi.iloc[-1]
    cci_curr = cci.iloc[-1]
    macd_hist_curr = macd_hist.iloc[-1]
    # Посмотрим просто направление MACD: рост или падение
    macd_trend_up = macd_hist_curr > 0
    macd_trend_down = macd_hist_curr < 0
    close_curr = close.iloc[-1]
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]

    cvd_positive = cvd > 0
    cvd_negative = cvd < 0
    oi_rising = oi_delta > 0
    oi_falling = oi_delta < 0

    # Добавим небольшую дельту для допуска при BB
    bb_delta = (bb_upper - bb_lower) * 0.1  # 10% ширины полосы

    # Смягчённые условия для входа в LONG
    long_entry = (
        (rsi_curr < 40 or cci_curr < -80) and
        macd_trend_up and
        close_curr <= bb_lower + bb_delta and
        cvd_positive and
        oi_rising
    )

    # Смягчённые условия выхода из LONG
    long_exit = (
        (rsi_curr > 60 or cci_curr > 80) and
        macd_trend_down and
        close_curr >= bb_upper - bb_delta
    )

    # Смягчённые условия входа в SHORT
    short_entry = (
        (rsi_curr > 60 or cci_curr > 80) and
        macd_trend_down and
        close_curr >= bb_upper - bb_delta and
        cvd_negative and
        oi_falling
    )

    # Смягчённые условия выхода из SHORT
    short_exit = (
        (rsi_curr < 40 or cci_curr < -80) and
        macd_trend_up and
        close_curr <= bb_lower + bb_delta
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
