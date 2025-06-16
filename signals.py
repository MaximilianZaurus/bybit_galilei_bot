from pybit import usdt_perpetual
import pandas as pd
import ta
import time
from datetime import datetime, timedelta

# Bybit API (без API-ключей для публичных данных)
session = usdt_perpetual.HTTP(endpoint="https://api.bybit.com")

def get_klines(symbol, interval='1', limit=200):
    # Получаем свечи 1 минутные по умолчанию (можно менять)
    res = session.query_kline(symbol=symbol, interval=interval, limit=limit)
    if res['ret_code'] != 0:
        raise Exception(f"Ошибка API: {res['ret_msg']}")
    data = res['result']
    df = pd.DataFrame(data)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    # Приводим колонки к float
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
        df[col] = df[col].astype(float)
    return df

def get_trades(symbol, start_time, end_time, limit=1000):
    # Получаем сделки за период (макс 1000 за запрос)
    # Bybit API возвращает только последние сделки, поэтому фильтруем вручную
    res = session.query_recent_trading_records(symbol=symbol, limit=limit)
    if res['ret_code'] != 0:
        raise Exception(f"Ошибка API trades: {res['ret_msg']}")
    trades = res['result']
    trades_df = pd.DataFrame(trades)
    trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time'], unit='ms')
    trades_df = trades_df[(trades_df['trade_time'] >= start_time) & (trades_df['trade_time'] <= end_time)]
    trades_df['price'] = trades_df['price'].astype(float)
    trades_df['qty'] = trades_df['qty'].astype(float)
    trades_df['isBuyerMaker'] = trades_df['isBuyerMaker'].astype(bool)
    return trades_df

def calculate_cvd(trades_df):
    # CVD = сумма объёмов покупок - сумма объёмов продаж
    # isBuyerMaker=True — значит продавец инициатор, значит покупатель лонг
    # Т.к. биржа помечает maker'ов, то лонг — это когда isBuyerMaker=False
    buy_volume = trades_df[trades_df['isBuyerMaker'] == False]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker'] == True]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    # Разница Open Interest за последние window свечей
    if len(df) < window + 1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window-1]

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

    bb_delta = (bb_upper - bb_lower) * 0.1

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

def main():
    symbol = "ETHUSDT"
    interval = '1'  # 1 минутные свечи
    print(f"Запуск анализа для {symbol} с интервалом {interval} мин")

    # Получаем последние свечи
    df = get_klines(symbol, interval=interval, limit=200)

    # Определяем временные рамки для получения сделок (последние свечи)
    end_time = df['open_time'].iloc[-1] + pd.Timedelta(minutes=1)
    start_time = end_time - pd.Timedelta(minutes=5)  # последние 5 минут сделок

    trades_df = get_trades(symbol, start_time, end_time)

    cvd = calculate_cvd(trades_df)
    oi_delta = calculate_oi_delta(df, window=3)

    signals = analyze_signal(df, cvd=cvd, oi_delta=oi_delta)

    print("Текущие значения индикаторов:")
    for k, v in signals['details'].items():
        print(f"  {k}: {v}")

    print("\nСигналы:")
    print(f" ▶️ Вход в Лонг: {'✅' if signals['long_entry'] else '❌'}")
    print(f" ⏹️ Выход из Лонга: {'✅' if signals['long_exit'] else '❌'}")
    print(f" ▶️ Вход в Шорт: {'✅' if signals['short_entry'] else '❌'}")
    print(f" ⏹️ Выход из Шорта: {'✅' if signals['short_exit'] else '❌'}")

if __name__ == "__main__":
    main()
