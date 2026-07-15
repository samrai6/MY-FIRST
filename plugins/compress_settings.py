import json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


SETTINGS_FILE = "compress_settings.json"


def load_settings():
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)


@Client.on_message(filters.command("settings"))
async def settings_menu(client, message):

    settings = load_settings()

    await message.reply_text(
        f"⚙️ Compress Settings\n\n"
        f"🎞 Codec: {settings['vcodec']}\n"
        f"🎚 CRF: {settings['crf']}\n"
        f"🎨 Bit: {settings['pix_fmt']}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎞 Codec",
                        callback_data="change_codec"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🎚 CRF",
                        callback_data="change_crf"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🎨 Bit",
                        callback_data="change_bit"
                    )
                ]
            ]
        )
    )


@Client.on_callback_query()
async def settings_callback(client, query):

    settings = load_settings()

    if query.data == "change_codec":

        settings["vcodec"] = (
            "libx265"
            if settings["vcodec"] == "libx264"
            else "libx264"
        )

    elif query.data == "change_crf":

        settings["crf"] = (
            28
            if settings["crf"] == 24
            else 24
        )

    elif query.data == "change_bit":

        settings["pix_fmt"] = (
            "yuv420p10le"
            if settings["pix_fmt"] == "yuv420p"
            else "yuv420p"
        )

    else:
        return

    save_settings(settings)

    await query.answer("Updated ✅")
