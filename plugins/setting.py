from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json


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


@Client.on_message(filters.command("setting"))
async def setting_cmd(client, message):

    data = load_settings()

    await message.reply_text(
        f"⚙️ Compress Settings\n\n"
        f"🎬 Vcodec: {data['vcodec']}\n"
        f"🎚 CRF: {data['crf']}\n"
        f"🎨 Pixel: {data['pix_fmt']}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "H264 (x264)",
                        callback_data="codec_x264"
                    ),
                    InlineKeyboardButton(
                        "H265 (x265)",
                        callback_data="codec_x265"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "CRF 18",
                        callback_data="crf_18"
                    ),
                    InlineKeyboardButton(
                        "CRF 24",
                        callback_data="crf_24"
                    ),
                    InlineKeyboardButton(
                        "CRF 28",
                        callback_data="crf_28"
                    )
                ]
            ]
        )
    )


@Client.on_callback_query(filters.regex("^(codec_|crf_)"))
async def setting_callback(client, query: CallbackQuery):

    data = load_settings()

    if query.data.startswith("codec_"):
        codec = query.data.split("_")[1]

        if codec == "x264":
            data["vcodec"] = "libx264"

        elif codec == "x265":
            data["vcodec"] = "libx265"


    elif query.data.startswith("crf_"):
        crf = query.data.split("_")[1]
        data["crf"] = int(crf)


    save_settings(data)

    await query.answer("Settings Updated ✅")

    await query.message.edit_text(
        f"⚙️ Compress Settings Updated\n\n"
        f"🎬 Vcodec: {data['vcodec']}\n"
        f"🎚 CRF: {data['crf']}\n"
        f"🎨 Pixel: {data['pix_fmt']}"
    )
