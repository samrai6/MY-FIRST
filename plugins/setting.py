from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json

SETTINGS_FILE = "compress_settings.json"


def load_settings():

    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video"
    }

    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        for key, value in default.items():
            data.setdefault(key, value)

        return data

    except Exception:

        return default


def save_settings(data):

    with open(SETTINGS_FILE, "w") as f:
        json.dump(
            data,
            f,
            indent=4
        )


def upload_mode_text(mode):

    if mode == "document":
        return "📄 Document"

    return "🎬 Video"


def settings_keyboard(data):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎬 Video" +
                    (" ✅" if data["upload_mode"] == "video" else ""),
                    callback_data="uploadmode_video"
                ),

                InlineKeyboardButton(
                    "📄 Document" +
                    (" ✅" if data["upload_mode"] == "document" else ""),
                    callback_data="uploadmode_document"
                )
            ],

            [
                InlineKeyboardButton(
                    "H264 (x264)" +
                    (" ✅" if data["vcodec"] == "libx264" else ""),
                    callback_data="codec_x264"
                ),

                InlineKeyboardButton(
                    "H265 (x265)" +
                    (" ✅" if data["vcodec"] == "libx265" else ""),
                    callback_data="codec_x265"
                )
            ],

            [
                InlineKeyboardButton(
                    "CRF 18" +
                    (" ✅" if data["crf"] == 18 else ""),
                    callback_data="crf_18"
                ),

                InlineKeyboardButton(
                    "CRF 24" +
                    (" ✅" if data["crf"] == 24 else ""),
                    callback_data="crf_24"
                ),

                InlineKeyboardButton(
                    "CRF 28" +
                    (" ✅" if data["crf"] == 28 else ""),
                    callback_data="crf_28"
                )
            ]
        ]
    )


# =========================
# /SETTING
# =========================

@Client.on_message(
    filters.command("setting") & filters.private
)
async def setting_cmd(client, message):

    data = load_settings()

    await message.reply_text(

        "⚙️ Compress Settings\n\n"

        f"📤 Upload: {upload_mode_text(data['upload_mode'])}\n"
        f"🎬 Vcodec: {data['vcodec']}\n"
        f"🎚 CRF: {data['crf']}\n"
        f"🎨 Pixel: {data['pix_fmt']}",

        reply_markup=settings_keyboard(data)
    )


# =========================
# SETTINGS CALLBACK
# =========================

@Client.on_callback_query(
    filters.regex(
        r"^(codec_|crf_|uploadmode_)"
    )
)
async def setting_callback(client, query: CallbackQuery):

    data = load_settings()

    # Upload mode
    if query.data.startswith("uploadmode_"):

        mode = query.data.split("_", 1)[1]

        if mode == "video":
            data["upload_mode"] = "video"

        elif mode == "document":
            data["upload_mode"] = "document"

    # Codec
    elif query.data.startswith("codec_"):

        codec = query.data.split("_", 1)[1]

        if codec == "x264":
            data["vcodec"] = "libx264"

        elif codec == "x265":
            data["vcodec"] = "libx265"

    # CRF
    elif query.data.startswith("crf_"):

        crf = query.data.split("_", 1)[1]

        try:
            data["crf"] = int(crf)
        except Exception:
            pass

    save_settings(data)

    await query.answer(
        "Settings Updated ✅"
    )

    await query.message.edit_text(

        "⚙️ Compress Settings\n\n"

        f"📤 Upload: {upload_mode_text(data['upload_mode'])}\n"
        f"🎬 Vcodec: {data['vcodec']}\n"
        f"🎚 CRF: {data['crf']}\n"
        f"🎨 Pixel: {data['pix_fmt']}",

        reply_markup=settings_keyboard(data)
        )
