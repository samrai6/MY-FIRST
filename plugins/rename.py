import os
import shutil

from pyrogram import Client, filters

user_files = {}


@Client.on_message(filters.document)
async def file_handler(client, message):
    user_files[message.from_user.id] = message

    await message.reply_text(
        "📁 File received!\n\n"
        "✏️ Now send me the new file name."
    )


@Client.on_message(filters.text & ~filters.command("start"))
async def get_new_name(client, message):
    if message.from_user.id not in user_files:
        return

    new_name = message.text

    await message.reply_text(
        f"✅ New file name:\n{new_name}\n\n"
        "🚧 Actual rename feature will be added next."
    )
