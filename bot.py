import os
from threading import Thread

from flask import Flask
from pyrogram import Client, filters

from config import API_ID, API_HASH, BOT_TOKEN


# Flask (Render health check)
web = Flask(__name__)

@web.route("/")
def home():
    return "Rename Bot is running!"


def run_web():
    web.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )


Thread(target=run_web).start()


# Telegram Bot
app = Client(
    "rename_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 Hello! I am Rename Bot.\n\n"
        "Send me a file to rename."
    )


# File receive test
@app.on_message(filters.document)
async def file_handler(client, message):
    await message.reply_text(
        "📁 File received!\n\n"
        "Rename feature is ready to add."
    )


print("Bot Started Successfully!")

app.run()
