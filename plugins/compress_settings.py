import json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


SETTINGS_FILE = "compress_settings.json"


def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)

    except:
        return {
            "vcodec": "libx264",
            "crf": 24,
            "pix_fmt": "yuv420p"
        }


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
        f"🎨 Pixel: {settings['pix_fmt']}",
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
                        "🎨 Pixel",
                        callback_data="change_pixel"
                    )
                ]
            ]
        )
    )


@Client.on_callback_query(
    filters.regex("^(change_codec|change_crf|change_pixel)$")
)
async def settings_callback(client, query: CallbackQuery):

    settings = load_settings()


    if query.data == "change_codec":

        if settings["vcodec"] == "libx264":
            settings["vcodec"] = "libx265"
        else:
            settings["vcodec"] = "libx264"


    elif query.data == "change_crf":

        if settings["crf"] == 24:
            settings["crf"] = 28
        else:
            settings["crf"] = 24


    elif query.data == "change_pixel":

        if settings["pix_fmt"] == "yuv420p":
            settings["pix_fmt"] = "yuv420p10le"
        else:
            settings["pix_fmt"] = "yuv420p"


    save_settings(settings)


    await query.answer(
        "Updated ✅"
    )


    await query.message.edit_text(
        f"⚙️ Compress Settings Updated\n\n"
        f"🎞 Codec: {settings['vcodec']}\n"
        f"🎚 CRF: {settings['crf']}\n"
        f"🎨 Pixel: {settings['pix_fmt']}"
    )
