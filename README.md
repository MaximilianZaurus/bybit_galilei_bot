# 🔥 Bybit Liquidation Alert Bot

Telegram-бот для мониторинга ликвидаций, Funding Rate и Open Interest по монетам:
**BTC, AAVE, ETH, SOL, XMR**.

Уведомляет, если:
- объём ликвидаций за 5 минут превышает заданный порог,
- резко меняется Funding Rate,
- резко изменяется Open Interest.

## 📦 Стек

- Python 3.10+
- Telegram Bot API
- Bybit Public API
- Render (хостинг)

## ⚙️ Установка

1. Клонируй репозиторий:

```bash
git clone https://github.com/your-username/liquidation-alert-bot.git
cd liquidation-alert-bot
