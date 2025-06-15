# bot.py
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Привет! Я бот стратегии Galilei. Сигналы будут приходить автоматически.")

telegram_app.add_handler(CommandHandler("start", start))
