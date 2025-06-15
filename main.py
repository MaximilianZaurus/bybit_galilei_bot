{\rtf1\ansi\ansicpg1251\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 # main.py\
import os\
import asyncio\
from fastapi import FastAPI, Request\
from dotenv import load_dotenv\
from bot import telegram_app\
from scheduler import start_scheduler\
\
load_dotenv()\
\
app = FastAPI()\
\
@app.on_event("startup")\
async def startup_event():\
    asyncio.create_task(start_scheduler())\
\
@app.post(f"/webhook/\{os.getenv('TELEGRAM_TOKEN')\}")\
async def telegram_webhook(req: Request):\
    update = await req.json()\
    await telegram_app.update(update)\
    return \{"status": "ok"\}\
\
@app.get("/")\
def read_root():\
    return \{"status": "Galilei bot running"\}\
}