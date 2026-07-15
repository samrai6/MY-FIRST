import os
import subprocess
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


Thread(target=run_web, daemon=True).start()


# Telegram Bot
app = Client(
    "rename_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins")
)

print("Bot Started Successfully!")

# Check FFmpeg
try:
    result = subprocess.run(
        ["ffmpeg", "-version"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("========== FFMPEG FOUND ==========")
        print(result.stdout.splitlines()[0])
    else:
        print("========== FFMPEG ERROR ==========")
        print(result.stderr)

except FileNotFoundError:
    print("========== FFMPEG NOT FOUND ==========")

app.run()
