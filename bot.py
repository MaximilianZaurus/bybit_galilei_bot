from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
import os
import json

load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("CHAT_ID")
client = HTTP(testnet=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open("tickers.json") as f:
        tickers = json.load(f)

    msg = "🟢 Бот запущен\n"
    for ticker in tickers:
        price = client.get_ticker(category="linear", symbol=ticker)["result"]["list"][0]["lastPrice"]
        msg += f"{ticker}: {price}\n"
    await context.bot.send_message(chat_id=chat_id, text=msg)

app = ApplicationBuilder().token(bot_token).build()
app.add_handler(CommandHandler("start", start))
