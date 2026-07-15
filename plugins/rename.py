import os
import shutil

from pathlib import Path
from pyrogram import Client, filters
from config import DOWNLOAD_DIR

user_files = {}

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_media(message):
    return (
        message.document
        or message.video
        or message.audio
        or message.voice
        or message.animation
    )


@Client.on_message(
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.animation
)
async def file_handler(client, message):
    user_files[message.from_user.id] = {
        "message": message
    }

    await message.reply_text(
        "📁 File received!\n\n"
        "✏️ Now send me the new file name.\n\n"
        "Example:\nMovie 2026"
    )


@Client.on_message(filters.text & ~filters.command("start"))
async def get_new_name(client, message):
    if message.from_user.id not in user_files:
        return

    new_name = message.text.strip()

    user_files[message.from_user.id]["new_name"] = new_name

    await message.reply_text(
    f"✅ New file name:\n`{new_name}`\n\n"
    "⏳ Rename process will start in the next step."
)
