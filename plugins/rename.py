from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters

from pathlib import Path
import subprocess
import time
import asyncio
import json
import os

from config import DOWNLOAD_DIR, OWNER_ID, THUMB_FILE_ID


# =========================
# GLOBAL
# =========================

user_files = {}

SETTINGS_FILE = "compress_settings.json"
THUMB_SETTINGS_FILE = "thumbnail.json"
THUMB_FILE = str(Path(DOWNLOAD_DIR) / "thumbnail.jpg")

PERMANENT_METADATA = "@SKR"


# =========================
# SETTINGS
# =========================

def load_compress_settings():

    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video"
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


def get_upload_mode():

    settings = load_compress_settings()

    mode = str(
        settings.get("upload_mode", "video")
    ).strip().lower()

    if mode not in ("video", "document"):
        mode = "video"

    return mode


# =========================
# THUMBNAIL
# =========================

def load_thumbnail_file_id():

    if THUMB_FILE_ID:
        return THUMB_FILE_ID

    try:
        with open(THUMB_SETTINGS_FILE, "r") as f:
            data = json.load(f)

        return data.get("file_id")

    except Exception:
        return None


def save_thumbnail_file_id(file_id):

    try:
        Path(THUMB_SETTINGS_FILE).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(THUMB_SETTINGS_FILE, "w") as f:
            json.dump(
                {
                    "file_id": file_id
                },
                f,
                indent=4
            )

    except Exception:
        pass


async def get_thumbnail(client):

    file_id = load_thumbnail_file_id()

    if not file_id:
        return None

    try:

        Path(DOWNLOAD_DIR).mkdir(
            parents=True,
            exist_ok=True
        )

        if os.path.exists(THUMB_FILE):
            return THUMB_FILE

        result = await client.download_media(
            file_id,
            file_name=THUMB_FILE
        )

        if result and os.path.exists(THUMB_FILE):
            return THUMB_FILE

    except Exception:
        pass

    return None


# =========================
# DIRECTORY
# =========================

Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


# =========================
# DOWNLOAD
# =========================

async def download_file(client, message):

    return await message.download(
        file_name=DOWNLOAD_DIR
    )


# =========================
# UPLOAD
# =========================

async def upload_file(
    client,
    message,
    file_path,
    thumbnail=None
):

    upload_mode = get_upload_mode()

    file_path = Path(file_path)
    file_name = file_path.name

    # Filename shown as caption
    caption = f"📄 `{file_name}`"

    # =========================
    # VIDEO MODE
    # =========================

    if upload_mode == "video":

        try:

            if thumbnail and os.path.exists(thumbnail):

                try:

                    await message.reply_video(
                        video=str(file_path),
                        thumb=thumbnail,
                        caption=caption
                    )

                except Exception:

                    await message.reply_video(
                        video=str(file_path),
                        caption=caption
                    )

            else:

                await message.reply_video(
                    video=str(file_path),
                    caption=caption
                )

            return True

        except Exception:

            # =========================
            # FALLBACK DOCUMENT
            # =========================

            try:

                await message.reply_document(
                    document=str(file_path),
                    caption=caption
                )

                return True

            except Exception:

                return False

    # =========================
    # DOCUMENT MODE
    # =========================

    try:

        if thumbnail and os.path.exists(thumbnail):

            try:

                await message.reply_document(
                    document=str(file_path),
                    thumb=thumbnail,
                    caption=caption
                )

                return True

            except Exception:
                pass

        await message.reply_document(
            document=str(file_path),
            caption=caption
        )

        return True

    except Exception:

        return False


# =========================
# SET THUMB
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


# =========================
# SAVE THUMBNAIL
# =========================

@Client.on_message(
    filters.photo & filters.private
)
async def save_thumbnail(client, message):

    if message.from_user.id != OWNER_ID:
        return

    file_id = message.photo.file_id

    save_thumbnail_file_id(file_id)

    try:

        Path(DOWNLOAD_DIR).mkdir(
            parents=True,
            exist_ok=True
        )

        if os.path.exists(THUMB_FILE):
            os.remove(THUMB_FILE)

        downloaded = await message.download(
            file_name=THUMB_FILE
        )

        if downloaded and os.path.exists(THUMB_FILE):
            pass

    except Exception:
        pass

    await message.reply_text(
        "✅ Thumbnail saved permanently!\n\n"
        "🎬 Video + 📄 Document\n"
        "🖼 Same thumbnail will be used automatically.\n\n"
        "You don't need to set it again."
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

        "output_file": None,

        "process": None,

        "cancelled": False
    }

    await message.reply_text(
        "📁 File received!\n\n"
        "✏️ Send new file name."
    )


# =========================
# GET NEW NAME
# =========================

@Client.on_message(
    filters.text &
    ~filters.command("start") &
    ~filters.command("setthumb") &
    ~filters.command("setting") &
    ~filters.command("settings")
)
async def get_new_name(client, message):

    uid = message.from_user.id

    if not message.text:
        return

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

    try:

        file_path = await download_file(
            client,
            user_files[uid]["message"]
        )

    except Exception as e:

        await message.reply_text(
            f"❌ Download failed.\n\n{e}"
        )

        user_files.pop(uid, None)

        return

    old_file = Path(file_path)

    # =========================
    # PRESERVE EXTENSION
    # =========================

    if Path(new_name).suffix:

        final_name = new_name

    else:

        final_name = (
            new_name +
            old_file.suffix
        )

    new_file = old_file.with_name(
        final_name
    )

    # =========================
    # RENAME
    # =========================

    try:

        if old_file.resolve() != new_file.resolve():

            if new_file.exists():
                new_file.unlink()

            old_file.rename(new_file)

    except Exception as e:

        await message.reply_text(
            f"❌ Rename failed.\n\n{e}"
        )

        try:

            if old_file.exists():
                old_file.unlink()

        except Exception:
            pass

        user_files.pop(uid, None)

        return

    user_files[uid]["file_path"] = str(new_file)
    user_files[uid]["cancelled"] = False

    await message.reply_text(

        "✏️ Rename completed!\n\n"
        f"📄 `{new_file.name}`\n\n"
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
# CALLBACK
# =========================

@Client.on_callback_query(
    filters.regex(
        r"^(compress|compress_\d+|rename_only|cancel_compress)$"
    )
)
async def action_handler(
    client,
    query: CallbackQuery
):

    uid = query.from_user.id

    if uid not in user_files:

        await query.answer(
            "Session expired. Send the file again.",
            show_alert=True
        )

        return

    await query.answer()

    # ==================================================
    # CANCEL
    # ==================================================

    if query.data == "cancel_compress":

        data = user_files.get(uid)

        if not data:
            return

        data["cancelled"] = True

        process = data.get("process")

        if process:

            try:

                if process.returncode is None:
                    process.kill()

            except Exception:
                pass

        try:

            await query.message.edit_text(
                "🛑 Cancelling compression..."
            )

        except Exception:
            pass

        return

    # ==================================================
    # RENAME ONLY
    # ==================================================

    if query.data == "rename_only":

        file_path = user_files[uid].get(
            "file_path"
        )

        if not file_path:

            await query.message.reply_text(
                "❌ File not found."
            )

            return

        if not os.path.exists(file_path):

            await query.message.reply_text(
                "❌ File not found."
            )

            return

        source = Path(file_path)

        upload_mode = get_upload_mode()

        # =========================
        # STATUS
        # =========================

        try:

            await query.message.edit_text(
                "✏️ Rename Only\n\n"
                f"📄 `{source.name}`\n"
                f"📤 Upload Mode: "
                f"{'🎬 Video' if upload_mode == 'video' else '📄 Document'}\n\n"
                "🔧 Adding metadata...\n"
                "📤 Uploading..."
            )

        except Exception:
            pass

        # =========================
        # THUMBNAIL
        # =========================

        thumbnail = await get_thumbnail(client)

        # =========================
        # VIDEO EXTENSIONS
        # =========================

        video_extensions = (
            ".mp4",
            ".mkv",
            ".mov",
            ".avi",
            ".webm",
            ".m4v",
            ".ts"
        )

        # ==================================================
        # METADATA REMUX
        # NO RE-ENCODING
        # ==================================================

        if source.suffix.lower() in video_extensions:

            metadata_file = source.with_name(
                f".{source.stem}_metadata{source.suffix}"
            )

            metadata_cmd = [

                "ffmpeg",

                "-hide_banner",

                "-loglevel",
                "error",

                "-i",
                str(source),

                "-map",
                "0",

                "-map_metadata",
                "0",

                "-metadata",
                f"comment={PERMANENT_METADATA}",

                "-c",
                "copy",

                "-y",

                str(metadata_file)
            ]

            try:

                result = await asyncio.to_thread(
                    subprocess.run,
                    metadata_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )

                if (
                    result.returncode == 0
                    and metadata_file.exists()
                    and metadata_file.stat().st_size > 0
                ):

                    os.replace(
                        metadata_file,
                        source
                    )

                else:

                    error_text = ""

                    if result.stderr:
                        error_text = result.stderr.decode(
                            "utf-8",
                            errors="ignore"
                        ).strip()

                    # Don't stop upload just because
                    # container doesn't support the tag
                    if error_text:

                        print(
                            "Metadata warning:",
                            error_text
                        )

            except Exception as e:

                print(
                    "Metadata exception:",
                    e
                )

            finally:

                try:

                    if metadata_file.exists():
                        metadata_file.unlink()

                except Exception:
                    pass

        # ==================================================
        # UPLOAD
        # ==================================================

        success = await upload_file(
            client,
            query.message,
            source,
            thumbnail
        )

        if not success:

            try:

                await query.message.reply_text(
                    "❌ Upload failed."
                )

            except Exception:
                pass

            return

        # =========================
        # CLEANUP
        # =========================

        try:

            if source.exists():
                source.unlink()

        except Exception:
            pass

        user_files.pop(uid, None)

        return

    # ==================================================
    # COMPRESS MENU
    # ==================================================

    if query.data == "compress":

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

        return

    # ==================================================
    # COMPRESS
    # ==================================================

    if query.data.startswith("compress_"):

        quality = query.data.split(
            "_",
            1
        )[1]

        if quality not in (
            "360",
            "480",
            "720",
            "1080"
        ):

            await query.message.reply_text(
                "❌ Invalid quality."
            )

            return

        input_path = Path(
            user_files[uid]["file_path"]
        )

        if not input_path.exists():

            await query.message.reply_text(
                "❌ Input file not found."
            )

            return

        user_files[uid]["cancelled"] = False

        # =========================
        # OUTPUT
        # =========================

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p.mp4"
        )

        try:

            if output_file.exists():
                output_file.unlink()

        except Exception:
            pass

        # =========================
        # SETTINGS
        # =========================

        settings = load_compress_settings()

        upload_mode = get_upload_mode()

        vcodec = settings.get(
            "vcodec",
            "libx264"
        )

        crf = settings.get(
            "crf",
            24
        )

        pix_fmt = settings.get(
            "pix_fmt",
            "yuv420p"
        )

        # =========================
        # DURATION
        # =========================

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

            duration_result = await asyncio.to_thread(
                subprocess.check_output,
                duration_cmd,
                stderr=subprocess.DEVNULL
            )

            duration = float(
                duration_result.decode().strip()
            )

        except Exception:

            await query.message.reply_text(
                "❌ Unable to read video duration."
            )

            return

        if duration <= 0:
            duration = 1

        # =========================
        # FFMPEG
        # =========================

        cmd = [

            "ffmpeg",

            "-hide_banner",

            "-loglevel",
            "error",

            "-progress",
            "pipe:1",

            "-stats_period",
            "1",

            "-i",
            str(input_path),

            "-map",
            "0:v:0",

            "-map",
            "0:a?",

            "-vf",
            f"scale=-2:{quality}",

            "-c:v",
            vcodec,

            "-preset",
            "veryfast",

            "-crf",
            str(crf),

            "-pix_fmt",
            pix_fmt,

            "-c:a",
            "aac",

            "-b:a",
            "96k",

            # =========================
            # METADATA
            # =========================

            "-map_metadata",
            "0",

            "-metadata",
            f"comment={PERMANENT_METADATA}",

            # =========================
            # MP4
            # =========================

            "-movflags",
            "+faststart",

            "-y",

            str(output_file)
        ]

        # =========================
        # STATUS
        # =========================

        status = await query.message.reply_text(

            "🗜 Compressing...\n\n"
            f"🎬 Quality: {quality}p\n"
            f"🎞 Codec: {vcodec}\n"
            f"🎚 CRF: {crf}\n"
            f"?
