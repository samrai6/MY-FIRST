from pyrogram import Client, filters


@Client.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 Hello! I am Rename Bot.\n\n"
        "Send me a file to rename."
    )
