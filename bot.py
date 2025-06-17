import os
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # подстроено под твои переменные
CHAT_ID = os.getenv("CHAT_ID")      # обязательно укажи в .env id чата

# Создаем объект Application один раз
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Асинхронная функция отправки сообщений (чтобы импортировать в scheduler)
bot = Bot(token=BOT_TOKEN)
async def send_message(text: str):
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Привет! Я бот стратегии Galilei. Сигналы будут приходить автоматически.")

telegram_app.add_handler(CommandHandler("start", start))
