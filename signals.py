from pybit.unified_trading import HTTP
import pandas as pd
import ta

def get_klines(symbol, interval='15', limit=200):
    res = session.query_kline(symbol=symbol, interval=interval, limit=limit)
    if res['ret_code'] != 0:
        raise Exception(f"Ошибка API: {res['ret_msg']}")
    data = res['result']
    df = pd.DataFrame(data)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']:
        df[col] = df[col].astype(float)
    return df

def get_trades(symbol, start_time, end_time, limit=1000):
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
    buy_volume = trades_df[trades_df['isBuyerMaker'] == False]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker'] == True]['qty'].sum()
    return buy_volume - sell_volume

def calculate_oi_delta(df, window=3):
    if len(df) < window + 1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window-1]

def analyze_signal(df: pd.DataFrame, cvd: float = 0, oi_delta: float = 0) -> dict:
    close = df['close']
    high = df['high']
    low = df['low']

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_hist = ta.trend.MACD(close).macd_diff()
    adx = ta.trend.ADXIndicator(high, low, close, window=14).adx()

    rsi_curr = rsi.iloc[-1]
    macd_hist_curr = macd_hist.iloc[-1]
    adx_curr = adx.iloc[-1]
    close_curr = close.iloc[-1]

    cvd_positive = cvd > 0
    cvd_negative = cvd < 0
    oi_rising = oi_delta > 0
    oi_falling = oi_delta < 0

    # Логика входа — только если тренд выражен (ADX > 20)
    long_entry = (
        (adx_curr > 20) and
        (rsi_curr < 35) and
        (macd_hist_curr < 0 and macd_hist_curr > macd_hist.iloc[-2]) and
        cvd_positive and
        oi_rising
    )

    long_exit = (
        (adx_curr > 20) and
        (rsi_curr > 60 or macd_hist_curr < macd_hist.iloc[-2])
    )

    short_entry = (
        (adx_curr > 20) and
        (rsi_curr > 65) and
        (macd_hist_curr > 0 and macd_hist_curr < macd_hist.iloc[-2]) and
        cvd_negative and
        oi_falling
    )

    short_exit = (
        (adx_curr > 20) and
        (rsi_curr < 40 or macd_hist_curr > macd_hist.iloc[-2])
    )

    return {
        'long_entry': long_entry,
        'long_exit': long_exit,
        'short_entry': short_entry,
        'short_exit': short_exit,
        'details': {
            'rsi': rsi_curr,
            'macd_hist': macd_hist_curr,
            'adx': adx_curr,
            'close': close_curr,
            'cvd': cvd,
            'oi_delta': oi_delta
        }
    }

def main():
    global session
    session = HTTP(endpoint="https://api.bybit.com")

    symbol = "ETHUSDT"
    interval = '15'  # 15 минутный таймфрейм

    print(f"Запуск анализа для {symbol} с интервалом {interval} мин")

    df = get_klines(symbol, interval=interval, limit=200)

    end_time = df['open_time'].iloc[-1] + pd.Timedelta(minutes=15)
    start_time = end_time - pd.Timedelta(minutes=5)

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
