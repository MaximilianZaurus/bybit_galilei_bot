import os
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram import Update, Bot

# Переменные окружения
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Создаём приложение и бота
application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Galilei Bot активен!")

application.add_handler(CommandHandler("start", start))

# ✅ Добавляем функцию отправки сообщений
async def send_telegram_message(text: str):
    if CHAT_ID and bot:
        await bot.send_message(chat_id=CHAT_ID, text=text)
    else:
        print("TELEGRAM_CHAT_ID или бот не настроен.")
