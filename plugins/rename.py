from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters

from pathlib import Path
import shutil
import subprocess
import time
import asyncio
import json
import os

from config import DOWNLOAD_DIR, OWNER_ID, THUMB_FILE_ID


user_files = {}

SETTINGS_FILE = "compress_settings.json"
THUMB_SETTINGS_FILE = "thumbnail.json"
THUMB_FILE = str(Path(DOWNLOAD_DIR) / "thumbnail.jpg")


# =========================
# COMPRESS SETTINGS
# =========================

def load_compress_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)

    except:
        return {
            "vcodec": "libx264",
            "crf": 24,
            "pix_fmt": "yuv420p"
        }


# =========================
# THUMBNAIL SETTINGS
# =========================

def load_thumbnail_file_id():
    # Environment variable has priority
    if THUMB_FILE_ID:
        return THUMB_FILE_ID

    try:
        with open(THUMB_SETTINGS_FILE, "r") as f:
            data = json.load(f)

        return data.get("file_id")

    except:
        return None


def save_thumbnail_file_id(file_id):
    with open(THUMB_SETTINGS_FILE, "w") as f:
        json.dump(
            {
                "file_id": file_id
            },
            f
        )


async def get_thumbnail(client):
    file_id = load_thumbnail_file_id()

    if not file_id:
        return None

    try:
        # If thumbnail already exists, use it
        if os.path.exists(THUMB_FILE):
            return THUMB_FILE

        Path(DOWNLOAD_DIR).mkdir(
            parents=True,
            exist_ok=True
        )

        downloaded = await client.download_media(
            file_id,
            file_name=THUMB_FILE
        )

        return downloaded

    except Exception:
        return None


# =========================
# DOWNLOAD DIRECTORY
# =========================

Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


async def download_file(client, message):
    return await message.download(
        file_name=DOWNLOAD_DIR
    )


# =========================
# SET THUMBNAIL
# =========================

@Client.on_message(
    filters.command("setthumb") & filters.private
)
async def set_thumb_command(client, message):

    if message.from_user.id != OWNER_ID:
        await message.reply_text(
            "❌ You are not authorized to use this command."
        )
        return

    await message.reply_text(
        "🖼 Send the photo you want to use as thumbnail."
    )


@Client.on_message(
    filters.photo & filters.private
)
async def save_thumbnail(client, message):

    if message.from_user.id != OWNER_ID:
        return

    file_id = message.photo.file_id

    save_thumbnail_file_id(file_id)

    # Download immediately
    try:
        Path(DOWNLOAD_DIR).mkdir(
            parents=True,
            exist_ok=True
        )

        if os.path.exists(THUMB_FILE):
            os.remove(THUMB_FILE)

        await message.download(
            file_name=THUMB_FILE
        )

    except Exception:
        pass

    await message.reply_text(
        "✅ Thumbnail saved successfully!\n\n"
        "🎬 This thumbnail will be used automatically for video uploads."
    )


# =========================
# FILE RECEIVED
# =========================

@Client.on_message(
    filters.document |
    filters.video |
    filters.audio |
    filters.voice |
    filters.animation
)
async def file_handler(client, message):

    user_files[message.from_user.id] = {
        "message": message,
        "file_path": None,
        "output_file": None
    }

    await message.reply_text(
        "📁 File received!\n\n"
        "✏️ Send new file name."
    )


# =========================
# GET NEW FILE NAME
# =========================

@Client.on_message(
    filters.text &
    ~filters.command("start") &
    ~filters.command("setthumb")
)
async def get_new_name(client, message):

    uid = message.from_user.id

    # Ignore commands
    if message.text.startswith("/"):
        return

    if uid not in user_files:
        return

    new_name = message.text.strip()

    if not new_name:
        return

    await message.reply_text(
        "⬇️ Downloading..."
    )

    file_path = await download_file(
        client,
        user_files[uid]["message"]
    )

    old_file = Path(file_path)

    new_file = old_file.with_name(
        new_name + old_file.suffix
    )

    shutil.move(
        file_path,
        new_file
    )

    user_files[uid]["file_path"] = str(new_file)

    await message.reply_text(
        "Choose action:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🗜 Compress",
                        callback_data="compress"
                    ),
                    InlineKeyboardButton(
                        "📄 Rename Only",
                        callback_data="rename_only"
                    )
                ]
            ]
        )
    )


# =========================
# CALLBACK HANDLER
# =========================

@Client.on_callback_query(
    filters.regex(
        "^(compress|compress_|rename_only|upload_)"
    )
)
async def action_handler(client, query: CallbackQuery):

    uid = query.from_user.id

    if uid not in user_files:
        return

    # =========================
    # RENAME ONLY
    # =========================

    if query.data == "rename_only":

        await query.message.reply_document(
            document=user_files[uid]["file_path"],
            caption="📄 Rename completed ✅"
        )

    # =========================
    # COMPRESS MENU
    # =========================

    elif query.data == "compress":

        await query.message.reply_text(
            "🗜 Select quality:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "360p",
                            callback_data="compress_360"
                        ),
                        InlineKeyboardButton(
                            "480p",
                            callback_data="compress_480"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "720p",
                            callback_data="compress_720"
                        ),
                        InlineKeyboardButton(
                            "1080p",
                            callback_data="compress_1080"
                        )
                    ]
                ]
            )
        )

    # =========================
    # COMPRESS
    # =========================

    elif query.data.startswith("compress_"):

        quality = query.data.split("_")[1]

        input_path = Path(
            user_files[uid]["file_path"]
        )

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p{input_path.suffix}"
        )

        settings = load_compress_settings()

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-progress",
            "pipe:1",
            "-stats_period",
            "1",
            "-i",
            str(input_path),
            "-vf",
            f"scale=-2:{quality}",
            "-c:v",
            settings["vcodec"],
            "-preset",
            "veryfast",
            "-crf",
            str(settings["crf"]),
            "-pix_fmt",
            settings["pix_fmt"],
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            "-y",
            str(output_file)
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        status = await query.message.reply_text(
            "🗜 Compressing...\n📊 Progress: 0%"
        )

        duration_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path)
        ]

        try:
            duration = float(
                subprocess.check_output(
                    duration_cmd
                ).decode().strip()
            )

        except:

            await status.edit_text(
                "❌ Unable to read video duration."
            )

            process.kill()
            return

        start = time.time()

        while True:

            line = process.stdout.readline()

            if not line and process.poll() is not None:
                break

            line = line.strip()

            if line.startswith("out_time_ms="):

                value = line.split("=")[1]

                if value == "N/A":
                    continue

                try:
                    current = int(value) / 1000000

                except ValueError:
                    continue

                percent = min(
                    int((current / duration) * 100),
                    100
                )

                elapsed = int(
                    time.time() - start
                )

                try:

                    await status.edit_text(
                        f"🗜 Compressing {quality}p...\n\n"
                        f"📊 Progress: {percent}%\n"
                        f"🎚 CRF: {settings['crf']}\n"
                        f"⚙️ Codec: {settings['vcodec']}\n"
                        f"⏱ Elapsed: {elapsed}s"
                    )

                except:
                    pass

        await asyncio.to_thread(
            process.wait
        )

        elapsed = int(
            time.time() - start
        )

        if process.returncode != 0:

            await status.edit_text(
                "❌ Compression Failed"
            )

            return

        user_files[uid]["output_file"] = str(
            output_file
        )

        await status.edit_text(
            f"✅ Compression Done\n\n"
            f"🎬 Quality: {quality}p\n"
            f"🎚 CRF: {settings['crf']}\n"
            f"⚙️ Codec: {settings['vcodec']}\n"
            f"⏱ Time: {elapsed}s",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📄 Document",
                            callback_data="upload_document"
                        ),
                        InlineKeyboardButton(
                            "🎬 Video",
                            callback_data="upload_video"
                        )
                    ]
                ]
            )
        )

    # =========================
    # UPLOAD DOCUMENT
    # =========================

    elif query.data == "upload_document":

        await query.message.reply_document(
            document=user_files[uid]["output_file"],
            caption="📄 Upload completed ✅"
        )

    # =========================
    # UPLOAD VIDEO + THUMB
    # =========================

    elif query.data == "upload_video":

        thumbnail = await get_thumbnail(client)

        if thumbnail:

            await query.message.reply_video(
                video=user_files[uid]["output_file"],
                thumb=thumbnail,
                caption="🎬 Upload completed ✅"
            )

        else:

            await query.message.reply_video(
                video=user_files[uid]["output_file"],
                caption="🎬 Upload completed ✅"
            )
