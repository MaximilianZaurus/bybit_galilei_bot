import json
import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from signals import analyze_signal  # ваша функция анализа

session = HTTP(testnet=False)  # реальный режим

def load_tickers():
    with open('tickers.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_klines(symbol, interval='15m', limit=2000):
    res = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,  # формат '15m', '1h' и т.п.
        limit=limit
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Kline API: {res.get('retMsg')}")

    kl = res['result']['list']
    df = pd.DataFrame(kl, columns=['open_time','open','high','low','close','volume','turnover'])
    df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
    df[['open','high','low','close','volume','turnover']] = df[['open','high','low','close','volume','turnover']].astype(float)
    return df

def get_open_interest(symbol, interval='15m'):
    res = session.get_open_interest(
        category="linear",
        symbol=symbol,
        interval=interval,       # must be like '15m'
        intervalTime=interval    # redundant fields but required
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"OI API: {res.get('retMsg')}")

    oi_list = res['result']['list']
    if not oi_list:
        raise Exception(f"Пустой OI ответ")

    df = pd.DataFrame(oi_list)
    df['open_time'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    df['open_interest'] = df['openInterest'].astype(float)
    return df[['open_time','open_interest']]

def calculate_oi_delta(kl_df, oi_df, window=3):
    # объединяем OI по времени свечей
    df = pd.merge(kl_df[['open_time']], oi_df, on='open_time', how='left').fillna(method='ffill')
    if len(df) < window+1:
        return 0
    return df['open_interest'].iloc[-1] - df['open_interest'].iloc[-window-1]

def get_trades(symbol, start, end, limit=2000):
    res = session.get_public_trading_records(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    if res.get('retCode', 1) != 0:
        raise Exception(f"Trades API: {res.get('retMsg')}")

    tr = res['result']['list']
    df = pd.DataFrame(tr)
    df['trade_time'] = pd.to_datetime(df['execTime'].astype(float), unit='ms')
    df = df[(df['trade_time'] >= start) & (df['trade_time'] < end)]
    df[['price','qty']] = df[['price','qty']].astype(float)
    df['isBuyerMaker'] = df['side']=='Sell'
    return df

def calculate_cvd(trades_df):
    return trades_df.loc[~trades_df['isBuyerMaker'],'qty'].sum() - trades_df.loc[trades_df['isBuyerMaker'],'qty'].sum()

def analyze_week(symbol):
    now = datetime.utcnow()
    start = now - timedelta(days=7)
    kl = get_klines(symbol, interval='15m')
    kl = kl[(kl['open_time'] >= start) & (kl['open_time'] < now)].reset_index(drop=True)

    oi = get_open_interest(symbol, interval='15m')
    long_c = short_c = 0

    for idx in range(50, len(kl)):
        slice_df = kl.iloc[max(0, idx-200):idx+1]
        t0 = slice_df['open_time'].iloc[-1]
        trades = get_trades(symbol, t0, t0 + timedelta(minutes=15))
        cvd = calculate_cvd(trades)
        oi_delta = calculate_oi_delta(slice_df, oi)

        sig = analyze_signal(slice_df, cvd=cvd, oi_delta=oi_delta)
        if sig.get('long_entry'):  long_c +=1
        if sig.get('short_entry'): short_c +=1

    print(f"{symbol}: Long entries={long_c}, Short entries={short_c}")

if __name__ == "__main__":
    for s in load_tickers():
        try:
            analyze_week(s)
        except Exception as e:
            print(f"Ошибка {s}: {e}")
