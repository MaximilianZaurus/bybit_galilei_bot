import pandas as pd
import ta
from pybit.unified_trading import HTTP

# Инициализация клиента Bybit (впиши свои ключи и endpoint)
client = HTTP(
    endpoint="https://api.bybit.com",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET"
)

def fetch_klines_with_oi(symbol: str, interval: str = "1", limit: int = 20) -> pd.DataFrame:
    """
    Получить свечи с Open Interest и вернуть в DataFrame.
    """
    response = client.get_kline(
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    data = response['result']
    # Собираем данные в DataFrame
    df = pd.DataFrame(data)
    # Приводим колонки к нужным типам
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['open_interest'] = df['open_interest'].astype(float)
    return df

def calculate_oi_delta(df: pd.DataFrame, periods: int = 3) -> float:
    """
    Считаем дельту OI за последние `periods` свечей.
    """
    if len(df) < periods + 1:
        return 0.0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-1 - periods]

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

    macd_trend_up = macd_hist_curr > 0
    macd_trend_down = macd_hist_curr < 0
    close_curr = close.iloc[-1]
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]

    cvd_positive = cvd > 0
    cvd_negative = cvd < 0
    oi_rising = oi_delta > 0
    oi_falling = oi_delta < 0

    bb_delta = (bb_upper - bb_lower) * 0.1  # 10% ширины полосы

    long_entry = (
        (rsi_curr < 40 or cci_curr < -80) and
        macd_trend_up and
        close_curr <= bb_lower + bb_delta and
        cvd_positive and
        oi_rising
    )

    long_exit = (
        (rsi_curr > 60 or cci_curr > 80) and
        macd_trend_down and
        close_curr >= bb_upper - bb_delta
    )

    short_entry = (
        (rsi_curr > 60 or cci_curr > 80) and
        macd_trend_down and
        close_curr >= bb_upper - bb_delta and
        cvd_negative and
        oi_falling
    )

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

# Пример использования
if __name__ == "__main__":
    symbol = "ETHUSDT"
    interval = "1"  # минутные свечи

    df = fetch_klines_with_oi(symbol, interval)
    oi_delta = calculate_oi_delta(df, periods=3)
    # CVD нужно передавать извне, здесь просто 0
    cvd = 0.0

    signals = analyze_signal(df, cvd=cvd, oi_delta=oi_delta)
    print(signals)
