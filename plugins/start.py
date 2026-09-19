from pyrogram import Client, filters


@Client.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 Welcome to SKR FILES!\n\n"
        "📁 Send me any file.\n\n"
        "1️⃣ Send the file\n"
        "2️⃣ Send the new filename\n"
        "3️⃣ Choose ✏️ Rename or 🗜️ Compress\n\n"
        "🚀 Simple & Fast"
    )
