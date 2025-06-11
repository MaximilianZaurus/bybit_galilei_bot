import requests
import time
import telegram
from datetime import datetime, timezone
import logging

# --- Настройки ---
TELEGRAM_TOKEN = '8054456169:AAFam6kFVbW6GJFZjNCip18T-geGUAk4kwA'
TELEGRAM_CHAT_ID = 5309903897

SYMBOLS = {
    'BTCUSDT': 'BTC',
    'AAVEUSDT': 'AAVE',
    'ETHUSDT': 'ETH',
    'SOLUSDT': 'SOL',
    'XMRUSDT': 'XMR'
}

# Пороговые объёмы ликвидаций (примерные, USD за 5 минут)
LIQUIDATION_THRESHOLDS = {
    'BTCUSDT': 1_000_000,
    'AAVEUSDT': 200_000,
    'ETHUSDT': 700_000,
    'SOLUSDT': 150_000,
    'XMRUSDT': 100_000,
}

# Частота проверки в секундах
CHECK_INTERVAL = 300  # 5 минут

# Bybit API endpoints
BYBIT_BASE = 'https://api.bybit.com'

# Инициализация бота Telegram
bot = telegram.Bot(token=TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

def send_telegram_message(text: str):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown')
        logging.info("Telegram message sent.")
    except Exception as e:
        logging.error(f"Error sending telegram message: {e}")

def get_current_timestamp_ms():
    return int(time.time() * 1000)

def fetch_liquidations(symbol: str, start_time_ms: int, end_time_ms: int):
    """
    Получить ликвидации с Bybit за период [start_time_ms, end_time_ms]
    """
    url = f"{BYBIT_BASE}/public/linear/liquidation/list"
    params = {
        'symbol': symbol,
        'start_time': start_time_ms // 1000,
        'end_time': end_time_ms // 1000,
        'limit': 50
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get('ret_code') == 0:
            return data['result']['data']
        else:
            logging.error(f"Bybit API error for {symbol}: {data.get('ret_msg')}")
            return []
    except Exception as e:
        logging.error(f"Exception fetching liquidations for {symbol}: {e}")
        return []

def fetch_funding_rate(symbol: str):
    """
    Получить последний Funding Rate с Bybit
    """
    url = f"{BYBIT_BASE}/public/linear/funding/prev-funding-rate"
    params = {'symbol': symbol}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get('ret_code') == 0 and data['result']:
            return float(data['result']['funding_rate'])
        else:
            logging.error(f"Funding Rate API error for {symbol}: {data.get('ret_msg')}")
            return None
    except Exception as e:
        logging.error(f"Exception fetching funding rate for {symbol}: {e}")
        return None

def fetch_open_interest(symbol: str):
    """
    Получить Open Interest с Bybit
    """
    url = f"{BYBIT_BASE}/public/linear/open-interest"
    params = {'symbol': symbol}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get('ret_code') == 0 and data['result']:
            return float(data['result']['open_interest'])
        else:
            logging.error(f"Open Interest API error for {symbol}: {data.get('ret_msg')}")
            return None
    except Exception as e:
        logging.error(f"Exception fetching open interest for {symbol}: {e}")
        return None

def summarize_liquidations(liquidations):
    """
    Подсчитать суммарный объём ликвидаций (USD) по лонгам и шортам
    """
    long_liq = 0
    short_liq = 0
    for liq in liquidations:
        qty = float(liq['qty'])
        price = float(liq['price'])
        side = liq['side']
        amount = qty * price
        if side == 'Buy':
            # Ликвидация лонга — покупка для закрытия позиции
            long_liq += amount
        elif side == 'Sell':
            # Ликвидация шорта — продажа для закрытия позиции
            short_liq += amount
    return long_liq, short_liq

def main():
    last_funding_rates = {}
    last_open_interest = {}

    logging.info("Bot started.")
    send_telegram_message("🚀 Bot for monitoring Bybit liquidations started.")

    while True:
        try:
            now_ms = get_current_timestamp_ms()
            start_ms = now_ms - CHECK_INTERVAL * 1000

            for symbol in SYMBOLS.keys():
                liquidations = fetch_liquidations(symbol, start_ms, now_ms)
                long_liq, short_liq = summarize_liquidations(liquidations)
                total_liq = long_liq + short_liq

                funding_rate = fetch_funding_rate(symbol)
                open_interest = fetch_open_interest(symbol)

                # Проверяем превышение порога ликвидаций
                threshold = LIQUIDATION_THRESHOLDS.get(symbol, 100_000)
                if total_liq >= threshold:
                    msg = (f"🔥 *{SYMBOLS[symbol]}* Liquidations Alert!\n"
                           f"Total Volume: ${total_liq:,.0f}\n"
                           f"Longs Liquidated: ${long_liq:,.0f}\n"
                           f"Shorts Liquidated: ${short_liq:,.0f}\n"
                           f"Funding Rate: {funding_rate if funding_rate is not None else 'N/A'}\n"
                           f"Open Interest: {open_interest if open_interest is not None else 'N/A'}\n"
                           f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    send_telegram_message(msg)

                # Funding rate резкие изменения
                if funding_rate is not None:
                    last_fr = last_funding_rates.get(symbol)
                    if last_fr is not None:
                        diff = abs(funding_rate - last_fr)
                        if diff > 0.0005:  # порог изменения funding rate
                            msg = (f"📈 *{SYMBOLS[symbol]}* Funding Rate changed significantly!\n"
                                   f"Previous: {last_fr:.6f}\n"
                                   f"Current: {funding_rate:.6f}\n"
                                   f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                            send_telegram_message(msg)
                    last_funding_rates[symbol] = funding_rate

                # Open Interest резкие изменения
                if open_interest is not None:
                    last_oi = last_open_interest.get(symbol)
                    if last_oi is not None:
                        change = (open_interest - last_oi) / last_oi if last_oi > 0 else 0
                        if abs(change) > 0.05:  # изменение более 5%
                            msg = (f"⚠️ *{SYMBOLS[symbol]}* Open Interest changed by {change:.2%}!\n"
                                   f"Previous: {last_oi:,.0f}\n"
                                   f"Current: {open_interest:,.0f}\n"
                                   f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                            send_telegram_message(msg)
                    last_open_interest[symbol] = open_interest

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
