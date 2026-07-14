
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from flask import Flask
from threading import Thread

web = Flask(__name__)

@web.route("/")
def home():
    return "Rename Bot is running!"

def run_web():
    web.run(host="0.0.0.0", port=8080)


Thread(target=run_web).start()


app = Client(
    "rename_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 Hello! I am Rename Bot.")


app.run()
