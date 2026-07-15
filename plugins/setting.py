from pyrogram import Client, filters
from pyrogram.types import Message
import json

SETTINGS_FILE = "compress_settings.json"


@Client.on_message(filters.command("setting"))
async def compress_setting(client, message: Message):

    with open(SETTINGS_FILE, "r") as f:
        data = json.load(f)

    await message.reply_text(
        f"⚙️ Compress Settings\n\n"
        f"🎬 Vcodec: {data['vcodec']}\n"
        f"🎚 CRF: {data['crf']}\n"
        f"🎨 Pixel Format: {data['pix_fmt']}"
    )
