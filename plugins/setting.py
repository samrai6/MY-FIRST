from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json


SETTINGS_FILE = "compress_settings.json"


def load_settings():

    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video",

        # New settings
        "resolution": "720p",
        "video_quality": "balanced",
        "audio_bitrate": "128k"
    }

    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            data = {}

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


def quality_text(quality):

    names = {
        "high": "High",
        "balanced": "Balanced",
        "small": "Small",
        "verysmall": "Very Small"
    }

    return names.get(
        quality,
        "Balanced"
    )


def settings_keyboard(data):

    return InlineKeyboardMarkup(
        [

            # Upload mode
            [
                InlineKeyboardButton(
                    "🎬 Video" +
                    (
                        " ✅"
                        if data["upload_mode"] == "video"
                        else ""
                    ),
                    callback_data="uploadmode_video"
                ),

                InlineKeyboardButton(
                    "📄 Document" +
                    (
                        " ✅"
                        if data["upload_mode"] == "document"
                        else ""
                    ),
                    callback_data="uploadmode_document"
                )
            ],

            # Codec
            [
                InlineKeyboardButton(
                    "H264 (x264)" +
                    (
                        " ✅"
                        if data["vcodec"] == "libx264"
                        else ""
                    ),
                    callback_data="codec_x264"
                ),

                InlineKeyboardButton(
                    "H265 (x265)" +
                    (
                        " ✅"
                        if data["vcodec"] == "libx265"
                        else ""
                    ),
                    callback_data="codec_x265"
                )
            ],

            # Resolution
            [
                InlineKeyboardButton(
                    "📐 Original" +
                    (
                        " ✅"
                        if data["resolution"] == "original"
                        else ""
                    ),
                    callback_data="resolution_original"
                )
            ],

            [
                InlineKeyboardButton(
                    "1080p" +
                    (
                        " ✅"
                        if data["resolution"] == "1080p"
                        else ""
                    ),
                    callback_data="resolution_1080p"
                ),

                InlineKeyboardButton(
                    "720p" +
                    (
                        " ✅"
                        if data["resolution"] == "720p"
                        else ""
                    ),
                    callback_data="resolution_720p"
                ),

                InlineKeyboardButton(
                    "480p" +
                    (
                        " ✅"
                        if data["resolution"] == "480p"
                        else ""
                    ),
                    callback_data="resolution_480p"
                )
            ],

            # Video quality
            [
                InlineKeyboardButton(
                    "🎚 High" +
                    (
                        " ✅"
                        if data["video_quality"] == "high"
                        else ""
                    ),
                    callback_data="vquality_high"
                ),

                InlineKeyboardButton(
                    "Balanced" +
                    (
                        " ✅"
                        if data["video_quality"] == "balanced"
                        else ""
                    ),
                    callback_data="vquality_balanced"
                )
            ],

            [
                InlineKeyboardButton(
                    "Small" +
                    (
                        " ✅"
                        if data["video_quality"] == "small"
                        else ""
                    ),
                    callback_data="vquality_small"
                ),

                InlineKeyboardButton(
                    "Very Small" +
                    (
                        " ✅"
                        if data["video_quality"] == "verysmall"
                        else ""
                    ),
                    callback_data="vquality_verysmall"
                )
            ],

            # Audio quality
            [
                InlineKeyboardButton(
                    "🔊 320k" +
                    (
                        " ✅"
                        if data["audio_bitrate"] == "320k"
                        else ""
                    ),
                    callback_data="audio_320k"
                ),

                InlineKeyboardButton(
                    "192k" +
                    (
                        " ✅"
                        if data["audio_bitrate"] == "192k"
                        else ""
                    ),
                    callback_data="audio_192k"
                ),

                InlineKeyboardButton(
                    "128k" +
                    (
                        " ✅"
                        if data["audio_bitrate"] == "128k"
                        else ""
                    ),
                    callback_data="audio_128k"
                )
            ],

            [
                InlineKeyboardButton(
                    "96k" +
                    (
                        " ✅"
                        if data["audio_bitrate"] == "96k"
                        else ""
                    ),
                    callback_data="audio_96k"
                ),

                InlineKeyboardButton(
                    "64k" +
                    (
                        " ✅"
                        if data["audio_bitrate"] == "64k"
                        else ""
                    ),
                    callback_data="audio_64k"
                )
            ],

            # Existing CRF settings
            [
                InlineKeyboardButton(
                    "CRF 18" +
                    (
                        " ✅"
                        if data["crf"] == 18
                        else ""
                    ),
                    callback_data="crf_18"
                ),

                InlineKeyboardButton(
                    "CRF 24" +
                    (
                        " ✅"
                        if data["crf"] == 24
                        else ""
                    ),
                    callback_data="crf_24"
                ),

                InlineKeyboardButton(
                    "CRF 28" +
                    (
                        " ✅"
                        if data["crf"] == 28
                        else ""
                    ),
                    callback_data="crf_28"
                )
            ]
        ]
    )


def settings_text(data):

    return (
        "⚙️ Compress Settings\n\n"

        f"📤 Upload: "
        f"{upload_mode_text(data['upload_mode'])}\n"

        f"🎬 Vcodec: "
        f"{data['vcodec']}\n"

        f"🎚 CRF: "
        f"{data['crf']}\n"

        f"🎨 Pixel: "
        f"{data['pix_fmt']}\n"

        f"📐 Resolution: "
        f"{data['resolution']}\n"

        f"🎚 Quality: "
        f"{quality_text(data['video_quality'])}\n"

        f"🔊 Audio: "
        f"{data['audio_bitrate']}"
    )


# =========================================================
# /SETTING
# =========================================================

@Client.on_message(
    filters.command("setting") & filters.private
)
async def setting_cmd(client, message):

    data = load_settings()

    await message.reply_text(
        settings_text(data),
        reply_markup=settings_keyboard(data)
    )


# =========================================================
# SETTINGS CALLBACK
# =========================================================

@Client.on_callback_query(
    filters.regex(
        r"^(codec_|crf_|uploadmode_|resolution_|vquality_|audio_)"
    )
)
async def setting_callback(
    client,
    query: CallbackQuery
):

    data = load_settings()

    # =====================================================
    # Upload Mode
    # =====================================================

    if query.data.startswith("uploadmode_"):

        mode = query.data.split(
            "_",
            1
        )[1]

        if mode in (
            "video",
            "document"
        ):
            data["upload_mode"] = mode

    # =====================================================
    # Codec
    # =====================================================

    elif query.data.startswith("codec_"):

        codec = query.data.split(
            "_",
            1
        )[1]

        if codec == "x264":

            data["vcodec"] = "libx264"

        elif codec == "x265":

            data["vcodec"] = "libx265"

    # =====================================================
    # Resolution
    # =====================================================

    elif query.data.startswith("resolution_"):

        resolution = query.data.split(
            "_",
            1
        )[1]

        if resolution in (
            "original",
            "1080p",
            "720p",
            "480p"
        ):
            data["resolution"] = resolution

    # =====================================================
    # Video Quality
    # =====================================================

    elif query.data.startswith("vquality_"):

        quality = query.data.split(
            "_",
            1
        )[1]

        quality_map = {
            "high": 18,
            "balanced": 24,
            "small": 28,
            "verysmall": 32
        }

        if quality in quality_map:

            data["video_quality"] = quality
            data["crf"] = quality_map[quality]

    # =====================================================
    # Audio Bitrate
    # =====================================================

    elif query.data.startswith("audio_"):

        bitrate = query.data.split(
            "_",
            1
        )[1]

        if bitrate in (
            "320k",
            "192k",
            "128k",
            "96k",
            "64k"
        ):
            data["audio_bitrate"] = bitrate

    # =====================================================
    # Existing CRF
    # =====================================================

    elif query.data.startswith("crf_"):

        crf = query.data.split(
            "_",
            1
        )[1]

        try:

            cr
