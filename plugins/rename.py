import asyncio
import json
import os
import re
import time
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from config import DOWNLOAD_DIR, OWNER_ID, THUMB_FILE_ID

from .compress import compress_file, cleanup_file
from .progress import (
    human_size,
    human_speed,
    human_time,
    progress_bar
)


# =========================
# GLOBAL
# =========================

user_files = {}

SETTINGS_FILE = "compress_settings.json"
THUMB_SETTINGS_FILE = "thumbnail.json"

THUMB_FILE = str(
    Path(DOWNLOAD_DIR) / "thumbnail.jpg"
)

PERMANENT_METADATA = "@SKR"

Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


# =========================
# SETTINGS
# =========================

def load_settings():

    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video"
    }

    try:
        with open(
            SETTINGS_FILE,
            "r"
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            data = {}

        for key, value in default.items():
            data.setdefault(
                key,
                value
            )

        return data

    except Exception:
        return default


def get_upload_mode():

    settings = load_settings()

    mode = str(
        settings.get(
            "upload_mode",
            "video"
        )
    ).lower().strip()

    if mode not in (
        "video",
        "document"
    ):
        mode = "video"

    return mode


# =========================
# THUMBNAIL
# =========================

def load_thumbnail_file_id():

    if THUMB_FILE_ID:
        return THUMB_FILE_ID

    try:
        with open(
            THUMB_SETTINGS_FILE,
            "r"
        ) as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data.get("file_id")

    except Exception:
        pass

    return None


def save_thumbnail_file_id(file_id):

    try:
        with open(
            THUMB_SETTINGS_FILE,
            "w"
        ) as f:
            json.dump(
                {
                    "file_id": file_id
                },
                f,
                indent=4
            )

    except Exception as e:
        print(
            "Thumbnail save error:",
            e
        )


async def get_thumbnail(client):

    file_id = load_thumbnail_file_id()

    if not file_id:
        return None

    try:

        Path(
            DOWNLOAD_DIR
        ).mkdir(
            parents=True,
            exist_ok=True
        )

        if os.path.exists(
            THUMB_FILE
        ):
            return THUMB_FILE

        result = await client.download_media(
            file_id,
            file_name=THUMB_FILE
        )

        if (
            result
            and os.path.exists(
                THUMB_FILE
            )
        ):
            return THUMB_FILE

    except Exception as e:
        print(
            "Thumbnail download error:",
            e
        )

    return None
# =========================
# SAFE FILENAME
# =========================

def safe_filename(name):

    name = str(name).strip()

    name = name.replace(
        "\x00",
        ""
    )

    name = re.sub(
        r'[\\/:*?"<>|]',
        "_",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    if not name:
        name = "file"

    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "LPT1",
        "LPT2",
        "LPT3"
    }

    if name.upper() in reserved:
        name = "_" + name

    return name[:180]


# =========================
# DOWNLOAD PROGRESS
# =========================

async def download_with_progress(
    message,
    source_message
):

    start_time = time.monotonic()
    last_update = 0

    async def progress(
        current,
        total
    ):

        nonlocal last_update

        now = time.monotonic()

        if (
            now - last_update < 2
            and current < total
        ):
            return

        last_update = now

        elapsed = max(
            now - start_time,
            0.001
        )

        percent = (
            current * 100 / total
            if total
            else 0
        )

        speed = current / elapsed

        eta = 0

        if speed > 0 and total:
            eta = max(
                total - current,
                0
            ) / speed

        bar = progress_bar(
            percent
        )

        text = (
            "⬇️ Downloading...\n\n"
            f"[{bar}] {percent:.1f}%\n\n"
            f"📦 {human_size(current)} / "
            f"{human_size(total)}\n"
            f"⚡ Speed: "
            f"{human_speed(speed)}\n"
            f"⏳ ETA: "
            f"{human_time(eta)}\n"
            f"🕐 Elapsed: "
            f"{human_time(elapsed)}"
        )

        try:
            await message.edit_text(
                text
            )
        except Exception:
            pass

    return await source_message.download(
        file_name=DOWNLOAD_DIR,
        progress=progress
    )


# =========================
# UPLOAD PROGRESS
# =========================

async def upload_progress(
    status,
    action,
    start_time
):

    last_update = {
        "time": 0
    }

    async def callback(
        current,
        total
    ):

        now = time.monotonic()

        if (
            now - last_update["time"] < 2
            and current < total
        ):
            return

        last_update["time"] = now

        elapsed = max(
            now - start_time,
            0.001
        )

        percent = (
            current * 100 / total
            if total
            else 0
        )

        speed = current / elapsed

        eta = 0

        if speed > 0 and total:
            eta = max(
                total - current,
                0
            ) / speed

        bar = progress_bar(
            percent
        )

        text = (
            f"{action}\n\n"
            f"[{bar}] {percent:.1f}%\n\n"
            f"📦 {human_size(current)} / "
            f"{human_size(total)}\n"
            f"⚡ Speed: "
            f"{human_speed(speed)}\n"
            f"⏳ ETA: "
            f"{human_time(eta)}\n"
            f"🕐 Elapsed: "
            f"{human_time(elapsed)}"
        )

        try:
            await status.edit_text(
                text
            )
        except Exception:
            pass

    return callback


# =========================
# UPLOAD FILE
# =========================

async def upload_file(
    client,
    status,
    file_path,
    thumbnail=None
):

    file_path = Path(
        file_path
    )

    if not file_path.exists():
        return False

    upload_mode = get_upload_mode()

    start_time = time.monotonic()

    if upload_mode == "video":

        try:

            progress = await upload_progress(
                status,
                "📤 Uploading Video...",
                start_time
            )

            kwargs = {
                "video": str(file_path),
                "progress": progress
            }

            if (
                thumbnail
                and os.path.exists(thumbnail)
            ):
                kwargs["thumb"] = thumbnail

            await status.reply_video(
                **kwargs
            )

            return True

        except Exception as e:

            print(
                "Video upload failed:",
                e
            )

            try:

                progress = await upload_progress(
                    status,
                    "📤 Uploading Document...",
                    start_time
                )

                await status.reply_document(
                    document=str(file_path),
                    progress=progress
                )

                return True

            except Exception as e2:

                print(
                    "Document fallback failed:",
                    e2
                )

                return False
    # =====================
    # DOCUMENT MODE
    # =====================

    try:

        progress = await upload_progress(
            status,
            "📤 Uploading Document...",
            start_time
        )

        if (
            thumbnail
            and os.path.exists(thumbnail)
        ):

            try:

                await status.reply_document(
                    document=str(file_path),
                    thumb=thumbnail,
                    progress=progress
                )

            except Exception as e:

                print(
                    "Document thumbnail failed:",
                    e
                )

                await status.reply_document(
                    document=str(file_path),
                    progress=progress
                )

        else:

            await status.reply_document(
                document=str(file_path),
                progress=progress
            )

        return True

    except Exception as e:

        print(
            "Document upload failed:",
            e
        )

        return False


# =========================
# FILE NAME
# =========================

def get_original_filename(message):

    if message.document:
        return message.document.file_name or "file"

    if message.video:
        return message.video.file_name or "video.mp4"

    if message.audio:
        return message.audio.file_name or "audio.mp3"

    if message.animation:
        return message.animation.file_name or "animation.mp4"

    return "file"


def get_extension(filename):

    suffix = Path(
        filename
    ).suffix.lower()

    if not suffix:
        return ""

    return suffix


def build_renamed_filename(
    original_name,
    new_name,
    quality=None
):

    original_ext = get_extension(
        original_name
    )

    new_name = safe_filename(
        new_name
    )

    if quality:
        new_name = (
            f"{new_name}_{quality}p"
        )

    if original_ext:
        return (
            f"{new_name}{original_ext}"
        )

    return new_name


# =========================
# RENAME ONLY
# =========================

@Client.on_message(
    filters.command("rename")
    & filters.private
)
async def rename_command(
    client,
    message
):

    reply = message.reply_to_message

    if not reply:

        await message.reply_text(
            "❌ Reply to a file/video and use:\n\n"
            "/rename New Name"
        )

        return

    command = message.text or ""

    parts = command.split(
        maxsplit=1
    )

    if len(parts) < 2:

        await message.reply_text(
            "❌ Give a new filename.\n\n"
            "Example:\n"
            "`/rename My Video`"
        )

        return

    new_name = parts[1].strip()

    if not new_name:

        await message.reply_text(
            "❌ Filename cannot be empty."
        )

        return

    status = await message.reply_text(
        "⬇️ Downloading..."
    )

    input_file = None
    output_file = None

    try:

        original_name = get_original_filename(
            reply
        )

        input_file = await download_with_progress(
            status,
            reply
        )

        if not input_file:

            raise RuntimeError(
                "Download failed."
            )

        input_path = Path(
            input_file
        )

        output_name = build_renamed_filename(
            original_name,
            new_name
        )

        output_file = (
            input_path.parent
            / output_name
        )

        if output_file.exists():
            output_file.unlink()

        input_path.rename(
            output_file
        )

        thumbnail = await get_thumbnail(
            client
        )

        await status.edit_text(
            "📤 Uploading..."
        )

        success = await upload_file(
            client,
            status,
            output_file,
            thumbnail
        )

        if not success:

            raise RuntimeError(
                "Upload failed."
            )

        try:
            await status.delete()
        except Exception:
            pass

    except Exception as e:

        print(
            "Rename error:",
            e
        )

        try:
            await status.edit_text(
                f"❌ Rename failed.\n\n"
                f"`{str(e)[:3000]}`"
            )
        except Exception:
            pass

    finally:

        try:
            if input_file:
                path = Path(
                    input_file
                )

                if path.exists():
                    path.unlink()

        except Exception:
            pass

        try:
            if output_file:

                path = Path(
                    output_file
                )

                if path.exists():
                    path.unlink()

        except Exception:
            pass


# =========================
# COMPRESS QUALITY MENU
# =========================

def quality_keyboard():

    return InlineKeyboardMarkup(
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
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="compress_cancel"
                )
            ]
        ]
    )

# =========================
# COMPRESS COMMAND
# =========================

@Client.on_message(
    filters.command("compress")
    & filters.private
)
async def compress_command(
    client,
    message
):

    reply = message.reply_to_message

    if not reply:

        await message.reply_text(
            "❌ Reply to a video and use:\n\n"
            "/compress"
        )

        return

    if not (
        reply.video
        or reply.document
        or reply.animation
    ):

        await message.reply_text(
            "❌ Please reply to a video file."
        )

        return

    user_id = message.from_user.id

    user_files[user_id] = {
        "message": reply,
        "cancel": asyncio.Event()
    }

    await message.reply_text(
        "🎬 Select compression quality:",
        reply_markup=quality_keyboard()
    )


# =========================
# COMPRESS CALLBACK
# =========================

@Client.on_callback_query(
    filters.regex(
        r"^compress_(360|480|720|1080|cancel)$"
    )
)
async def compress_callback(
    client,
    query: CallbackQuery
):

    user_id = query.from_user.id

    data = user_files.get(
        user_id
    )

    if not data:

        await query.answer(
            "❌ No active file.",
            show_alert=True
        )

        return

    if query.data == "compress_cancel":

        data["cancel"].set()

        user_files.pop(
            user_id,
            None
        )

        try:
            await query.message.edit_text(
                "🛑 Compression cancelled."
            )
        except Exception:
            pass

        await query.answer(
            "Cancelled"
        )

        return

    quality = query.data.split(
        "_"
    )[1]

    quality = int(
        quality
    )

    source_message = data["message"]
    cancel_event = data["cancel"]

    input_file = None
    output_file = None

    try:

        await query.answer(
            f"{quality}p selected ✅"
        )

        await query.message.edit_text(
            f"⬇️ Downloading source...\n\n"
            f"🎯 Target: {quality}p"
        )

        input_file = await download_with_progress(
            query.message,
            source_message
        )

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        if not input_file:
            raise RuntimeError(
                "Download failed."
            )

        input_path = Path(
            input_file
        )

        original_name = get_original_filename(
            source_message
        )

        stem = Path(
            original_name
        ).stem

        extension = (
            Path(original_name)
            .suffix
            .lower()
        )

        if not extension:
            extension = ".mp4"

        renamed_name = build_renamed_filename(
            original_name,
            stem,
            quality
        )

        output_file = (
            input_path.parent
            / renamed_name
        )

        if output_file.exists():
            output_file.unlink()

        await query.message.edit_text(
            f"🗜️ Starting compression...\n\n"
            f"🎯 Target: {quality}p\n"
            f"📄 `{renamed_name}`"
        )

        result = await compress_file(
            input_path,
            output_file,
            quality,
            query.message,
            cancel_event
        )

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        if not result:
            raise RuntimeError(
                "Compression failed."
            )

        thumbnail = await get_thumbnail(
            client
        )

        await query.message.edit_text(
            "📤 Preparing upload..."
        )

        success = await upload_file(
            client,
            query.message,
            output_file,
            thumbnail
        )

        if not success:
            raise RuntimeError(
                "Upload failed."
            )

        try:
            await query.message.delete()
        except Exception:
            pass

    except asyncio.CancelledError:

        try:
            await query.message.edit_text(
                "🛑 Compression cancelled."
            )
        except Exception:
            pass

    except Exception as e:

        print(
            "Compression error:",
            e
        )

        try:
            await query.message.edit_text(
                f"❌ Compression failed.\n\n"
                f"`{str(e)[:3000]}`"
            )
        except Exception:
            pass

    finally:

        try:
            if input_file:

                path = Path(
                    input_file
                )

                if path.exists():
                    path.unlink()

        except Exception:
            pass

        try:
            if output_file:

                path = Path(
                    output_file
                )

                if path.exists():
                    path.unlink()

        except Exception:
            pass

        user_files.pop(
            user_id,
            None
        )


# =========================
# CANCEL COMMAND
# =========================

@Client.on_message(
    filters.command("cancel")
    & filters.private
)
async def cancel_command(
    client,
    message
):

    user_id = message.from_user.id

    data = user_files.get(
        user_id
    )

    if not data:

        await message.reply_text(
            "ℹ️ No active compression."
        )

        return

    data["cancel"].set()

    await message.reply_text(
        "🛑 Cancellation requested..."
    )
