from pyrogram import Client, filters

user_files = {}

@Client.on_message(filters.document)
async def file_handler(client, message):
    await message.reply_text(
        "📁 File received!\n\n"
        "Rename feature is ready to add."
    )
