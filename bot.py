import os
from threading import Thread

from flask import Flask
from pyrogram import Client

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
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins")
)

print("Bot Started Successfully!")

app.run()
