from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os


SETTINGS_FILE = "settings.json"


def load_settings():
    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video",
        "resolution": "720p",
        "video_quality": "balanced",
        "audio_bitrate": "128k"
    }

    if not os.path.exists(SETTINGS_FILE):
        return default

    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        for key, value in default.items():
            if key not in data:
                data[key] = value

        return data

    except Exception:
        return default


def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def settings_keyboard(data):

    codec = data.get("vcodec", "libx264")
    upload = data.get("upload_mode", "video")
    resolution = data.get("resolution", "720p")
    video_quality = data.get("video_quality", "balanced")
    audio = data.get("audio_bitrate", "128k")
    crf = data.get("crf", 24)

    return InlineKeyboardMarkup([

        # Upload Mode
        [
            InlineKeyboardButton(
                f"🎬 Video {'✅' if upload == 'video' else ''}",
                callback_data="uploadmode_video"
            ),
            InlineKeyboardButton(
                f"📁 Document {'✅' if upload == 'document' else ''}",
                callback_data="uploadmode_document"
            )
        ],

        # Codec
        [
            InlineKeyboardButton(
                f"H264 {'✅' if codec == 'libx264' else ''}",
                callback_data="codec_x264"
            ),
            InlineKeyboardButton(
                f"H265 {'✅' if codec == 'libx265' else ''}",
                callback_data="codec_x265"
            )
        ],

        # Resolution
        [
            InlineKeyboardButton(
                f"Original {'✅' if resolution == 'original' else ''}",
                callback_data="resolution_original"
            ),
            InlineKeyboardButton(
                f"1080p {'✅' if resolution == '1080p' else ''}",
                callback_data="resolution_1080p"
            )
        ],
        [
            InlineKeyboardButton(
                f"720p {'✅' if resolution == '720p' else ''}",
                callback_data="resolution_720p"
            ),
            InlineKeyboardButton(
                f"480p {'✅' if resolution == '480p' else ''}",
                callback_data="resolution_480p"
            )
        ],

        # Video Quality
        [
            InlineKeyboardButton(
                f"🔥 High {'✅' if video_quality == 'high' else ''}",
                callback_data="vquality_high"
            ),
            InlineKeyboardButton(
                f"⚖️ Balanced {'✅' if video_quality == 'balanced' else ''}",
                callback_data="vquality_balanced"
            )
        ],
        [
            InlineKeyboardButton(
                f"📦 Small {'✅' if video_quality == 'small' else ''}",
                callback_data="vquality_small"
            ),
            InlineKeyboardButton(
                f"🗜️ Very Small {'✅' if video_quality == 'verysmall' else ''}",
                callback_data="vquality_verysmall"
            )
        ],

        # Audio
        [
            InlineKeyboardButton(
                f"🎵 320k {'✅' if audio == '320k' else ''}",
                callback_data="audio_320k"
            ),
            InlineKeyboardButton(
                f"🎵 192k {'✅' if audio == '192k' else ''}",
                callback_data="audio_192k"
            )
        ],
        [
            InlineKeyboardButton(
                f"🎵 128k {'✅' if audio == '128k' else ''}",
                callback_data="audio_128k"
            ),
            InlineKeyboardButton(
                f"🎵 96k {'✅' if audio == '96k' else ''}",
                callback_data="audio_96k"
            )
        ],
        [
            InlineKeyboardButton(
                f"🎵 64k {'✅' if audio == '64k' else ''}",
                callback_data="audio_64k"
            )
        ],

        # Original CRF settings
        [
            InlineKeyboardButton(
                f"CRF 18 {'✅' if crf == 18 else ''}",
                callback_data="crf_18"
            ),
            InlineKeyboardButton(
                f"CRF 24 {'✅' if crf == 24 else ''}",
                callback_data="crf_24"
            ),
            InlineKeyboardButton(
                f"CRF 28 {'✅' if crf == 28 else ''}",
                callback_data="crf_28"
            )
        ]
    ])


def settings_text(data):

    codec = "H264" if data.get("vcodec") == "libx264" else "H265"

    return (
        "⚙️ **Compression Settings**\n\n"
        f"📤 Upload Mode: `{data.get('upload_mode', 'video')}`\n"
        f"🎞 Codec: `{codec}`\n"
        f"📐 Resolution: `{data.get('resolution', '720p')}`\n"
        f"🔥 Video Quality: `{data.get('video_quality', 'balanced')}`\n"
        f"🎵 Audio Quality: `{data.get('audio_bitrate', '128k')}`\n"
        f"🎚 CRF: `{data.get('crf', 24)}`\n"
        f"🎨 Pixel Format: `{data.get('pix_fmt', 'yuv420p')}`"
    )


@Client.on_message(filters.command("setting"))
async def setting_command(client, message):

    data = load_settings()

    await message.reply_text(
        settings_text(data),
        reply_markup=settings_keyboard(data)
    )


@Client.on_callback_query(
    filters.regex(
        r"^(uploadmode_|codec_|resolution_|vquality_|audio_|crf_)"
    )
)
async def setting_callback(client, query):

    data = load_settings()
    action = query.data

    # Upload Mode
    if action == "uploadmode_video":
        data["upload_mode"] = "video"

    elif action == "uploadmode_document":
        data["upload_mode"] = "document"

    # Codec
    elif action == "codec_x264":
        data["vcodec"] = "libx264"

    elif action == "codec_x265":
        data["vcodec"] = "libx265"

    # Resolution
    elif action == "resolution_original":
        data["resolution"] = "original"

    elif action == "resolution_1080p":
        data["resolution"] = "1080p"

    elif action == "resolution_720p":
        data["resolution"] = "720p"

    elif action == "resolution_480p":
        data["resolution"] = "480p"

    # Video Quality
    elif action == "vquality_high":
        data["video_quality"] = "high"
        data["crf"] = 18

    elif action == "vquality_balanced":
        data["video_quality"] = "balanced"
        data["crf"] = 24

    elif action == "vquality_small":
        data["video_quality"] = "small"
        data["crf"] = 28

    elif action == "vquality_verysmall":
        data["video_quality"] = "verysmall"
        data["crf"] = 32

    # Audio
    elif action == "audio_320k":
        data["audio_bitrate"] = "320k"

    elif action == "audio_192k":
        data["audio_bitrate"] = "192k"

    elif action == "audio_128k":
        data["audio_bitrate"] = "128k"

    elif action == "audio_96k":
        data["audio_bitrate"] = "96k"

    elif action == "audio_64k":
        data["audio_bitrate"] = "64k"

    # CRF
    elif action == "crf_18":
        data["crf"] = 18
        data["video_quality"] = "high"

    elif action == "crf_24":
        data["crf"] = 24
        data["video_quality"] = "balanced"

    elif action == "crf_28":
        data["crf"] = 28
        data["video_quality"] = "small"

    save_settings(data)

    await query.answer("✅ Setting updated")

    await query.message.edit_text(
        settings_text(data),
        reply_markup=settings_keyboard(data)
    )
