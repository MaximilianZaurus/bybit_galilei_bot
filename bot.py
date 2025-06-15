{\rtf1\ansi\ansicpg1251\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 # bot.py\
import os\
from dotenv import load_dotenv\
from telegram import Update\
from telegram.ext import Application, CommandHandler, ContextTypes\
\
load_dotenv()\
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")\
\
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()\
\
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    await update.message.reply_text("\uc0\u55358 \u56598  \u1055 \u1088 \u1080 \u1074 \u1077 \u1090 ! \u1071  \u1073 \u1086 \u1090  \u1089 \u1090 \u1088 \u1072 \u1090 \u1077 \u1075 \u1080 \u1080  Galilei. \u1057 \u1080 \u1075 \u1085 \u1072 \u1083 \u1099  \u1073 \u1091 \u1076 \u1091 \u1090  \u1087 \u1088 \u1080 \u1093 \u1086 \u1076 \u1080 \u1090 \u1100  \u1072 \u1074 \u1090 \u1086 \u1084 \u1072 \u1090 \u1080 \u1095 \u1077 \u1089 \u1082 \u1080 .")\
\
telegram_app.add_handler(CommandHandler("start", start))\
}