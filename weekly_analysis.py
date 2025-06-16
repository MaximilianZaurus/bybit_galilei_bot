from pybit.unified_trading import HTTP
import pandas as pd
import ta
import json
from datetime import datetime, timedelta

# --- Загрузка тикеров из файла ---
def get_tickers():
    with open("tickers.json", "r") as f:
        return json.load(f)

# --- Инициализация сессии Bybit v5 ---
session = HTTP(testnet=False)  # Или testnet=True, если нужен тестнет

# --- Получение свечей (Klines) ---
def get_klines(symbol, interval='1h', limit=168):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )
    if res['retCode'] != 0:
        raise Exception(f"Kline API error: {res['retMsg']}")
    kline_list = res['result']['list']
    df = pd.DataFrame(kline_list)
    df['open_time'] = pd.to_datetime(df['openTime'].astype(float), unit='ms')
    # Приводим нужные колонки к float
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    return df[['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover']]

# --- Получение истории Open Interest ---
def get_open_interest(symbol, interval='1h'):
    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        intervalTime=interval  # Обязательно intervalTime (регистр!)
    )
    if res['retCode'] != 0:
        raise Exception(f"OI API error: {res['retMsg']}")
    df = pd.DataFrame(res['result']['list'])
    df['open_time'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time', 'open_interest']]

# --- Получение истории трейдов (trades) ---
def get_trades(symbol, start_time, end_time):
    res = session.get_trade_history(
        category="linear",
        symbol=symbol,
        limit=1000  # максимум за один запрос
    )
    if res['retCode'] != 0:
        raise Exception(f"Trade API error: {res['retMsg']}")
    df = pd.DataFrame(res['result']['list'])
    # В v5 колонка execTime в формате ISO или timestamp?
    # В docs execTime — timestamp в ms, преобразуем:
    df['trade_time'] = pd.to_datetime(df['execTime'].astype(float), unit='ms')
    # Фильтрация по времени
    df = df[(df['trade_time'] >= start_time) & (df['trade_time'] < end_time)]
    df['qty'] = df['execQty'].astype(float)
    # По документации: side 'Buy' или 'Sell'; isBuyerMaker = True если продажа (Sell)
    df['isBuyerMaker'] = df['side'] == 'Sell'
    return df

# --- Расчёт CVD ---
def calculate_cvd(trades_df):
    buy_volume = trades_df[~trades_df['isBuyerMaker']]['qty'].sum()
    sell_volume = trades_df[trades_df['isBuyerMaker']]['qty'].sum()
    return buy_volume - sell_volume

# --- Δ Open Interest за последние N свечей ---
def calculate_oi_delta(df, window=3):
    if len(df) < window + 1 or 'open_interest' not in df.columns:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window - 1]

# --- Анализ одного символа ---
def analyze_single_symbol(symbol: str) -> str:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    df = get_klines(symbol, interval='1h', limit=168)
    oi_df = get_open_interest(symbol, interval='1h')
    df = pd.merge(df, oi_df, on='open_time', how='left')
    df['open_interest'] = df['open_interest'].fillna(method='ffill')

    trades_df = get_trades(symbol, week_ago, now)
    cvd = calculate_cvd(trades_df)
    oi_delta = calculate_oi_delta(df)

    close = df['close']
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_hist = ta.trend.MACD(close).macd_diff().iloc[-1]
    macd_dir = "↑" if macd_hist > 0 else "↓"
    trend = "⏫ Uptrend" if macd_hist > 0 else "⏬ Downtrend"

    return f"{symbol}: RSI {rsi:.1f}, MACD {macd_hist:.3f} {macd_dir}, ΔOI {oi_delta:.1f}, CVD {cvd:.1f} {trend}"

# --- Основной недельный анализ ---
def analyze_week() -> str:
    tickers = get_tickers()
    result_lines = ["📊 Weekly Overview:"]
    for symbol in tickers:
        try:
            line = analyze_single_symbol(symbol)
            result_lines.append(line)
        except Exception as e:
            result_lines.append(f"{symbol}: ❌ Ошибка анализа: {e}")
    return "\n".join(result_lines)

# --- Запуск ---
if __name__ == "__main__":
    print(analyze_week())
