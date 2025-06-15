# bot.py
import os
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram import Update

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

application = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Galilei Bot активен!")

application.add_handler(CommandHandler("start", start))
