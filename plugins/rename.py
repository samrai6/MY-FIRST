from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import shutil

from pathlib import Path
from pyrogram import Client, filters
from config import DOWNLOAD_DIR

user_files = {}

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

def get_media(message):
    return (
        message.document
        or message.video
        or message.audio
        or message.voice
        or message.animation
    )
    
async def download_file(client, message):
    file_path = await message.download(
        file_name=DOWNLOAD_DIR
    )
    return file_path

@Client.on_message(
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.animation
)
async def file_handler(client, message):
    user_files[message.from_user.id] = {
    "message": message,
    "file_path": None,
    "new_name": None
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

    await message.reply_text(
    "⬇️ Downloading file...\n\n"
    "⏳ Please wait..."
    )
    [message.from_user.id]["new_name"] = new_name

    file_path = await download_file(
        client,
        user_files[message.from_user.id]["message"]
    )
    
await message.reply_text(
    "📝 Renaming file..."
)
    user_files[message.from_user.id]["file_path"] = file_path

    old_file = Path(file_path)

    extension = old_file.suffix

    new_file = old_file.with_name(
        new_name + extension
    )

    shutil.move(
        file_path,
        new_file
    )

    user_files[message.from_user.id]["file_path"] = str(new_file)

    await message.reply_text(
    "Choose action:",
    reply_markup=InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🗜 Compress", callback_data="compress"),
                InlineKeyboardButton("📄 Rename Only", callback_data="rename_only")
            ]
        ]
    )
    )
