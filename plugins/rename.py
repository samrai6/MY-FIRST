import os
import re
import json
import time
import asyncio
import subprocess
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# =========================
# CONFIG
# =========================

OWNER_ID = int(
    os.getenv(
        "OWNER_ID",
        "0"
    )
)

DOWNLOAD_DIR = os.getenv(
    "DOWNLOAD_DIR",
    "downloads"
)

SETTINGS_FILE = "compress_settings.json"
THUMB_SETTINGS_FILE = "thumbnail.json"

THUMB_FILE = str(
    Path(DOWNLOAD_DIR) / "thumbnail.jpg"
)

PERMANENT_METADATA = "@SKR"


# =========================
# GLOBALS
# =========================

user_files = {}

# Only one FFmpeg compression at a time
compression_lock = asyncio.Lock()


# =========================
# DIRECTORY
# =========================

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)


# =========================
# TIME FORMAT
# =========================

def format_time(seconds):

    try:
        seconds = int(
            max(
                0,
                seconds
            )
        )
    except Exception:
        return "00:00"

    hours = seconds // 3600
    minutes = (
        seconds % 3600
    ) // 60
    secs = seconds % 60

    if hours > 0:

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


# =========================
# FILE SIZE
# =========================

def format_bytes(size):

    try:
        size = float(size)
    except Exception:
        return "0 B"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ]

    for unit in units:

        if size < 1024:
            return (
                f"{size:.1f} {unit}"
                if unit != "B"
                else f"{int(size)} B"
            )

        size /= 1024

    return f"{size:.1f} PB"


# =========================
# SPEED
# =========================

def format_speed(
    current,
    previous,
    elapsed
):

    try:

        difference = (
            current - previous
        )

        if elapsed <= 0:
            return "0 B/s"

        speed = (
            difference / elapsed
        )

        return (
            f"{format_bytes(speed)}/s"
        )

    except Exception:

        return "0 B/s"


# =========================
# SAFE FILENAME
# =========================

def safe_filename(
    filename
):

    filename = str(
        filename
    ).strip()

    filename = filename.replace(
        "\\",
        "_"
    )

    filename = filename.replace(
        "/",
        "_"
    )

    filename = re.sub(
        r"[\x00-\x1f\x7f]",
        "_",
        filename
    )

    filename = re.sub(
        r'[<>:"|?*]',
        "_",
        filename
    )

    filename = filename.strip(
        ". "
    )

    if not filename:

        filename = "file"

    return filename[:180]


# =========================
# SAFE REMOVE
# =========================

def safe_remove(
    path
):

    if not path:
        return

    try:

        if os.path.exists(path):

            os.remove(path)

    except Exception as e:

        print(
            "Remove error:",
            e
        )


# =========================
# SETTINGS
# =========================

def load_compress_settings():

    defaults = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video"
    }

    try:

        if not os.path.exists(
            SETTINGS_FILE
        ):

            return defaults

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            settings = json.load(f)

        if not isinstance(
            settings,
            dict
        ):

            return defaults

        result = defaults.copy()

        result.update(
            settings
        )

        # Validate codec
        if result["vcodec"] not in (
            "libx264",
            "libx265"
        ):

            result["vcodec"] = (
                "libx264"
            )

        # Validate CRF
        try:

            result["crf"] = int(
                result["crf"]
            )

        except Exception:

            result["crf"] = 24

        result["crf"] = max(
            0,
            min(
                result["crf"],
                51
            )
        )

        # Validate pixel format
        if not result.get(
            "pix_fmt"
        ):

            result["pix_fmt"] = (
                "yuv420p"
            )

        # Validate upload mode
        if result.get(
            "upload_mode"
        ) not in (
            "video",
            "document"
        ):

            result["upload_mode"] = (
                "video"
            )

        return result

    except Exception as e:

        print(
            "Settings load error:",
            e
        )

        return defaults


# =========================
# UPLOAD MODE
# =========================

def get_upload_mode():

    settings = (
        load_compress_settings()
    )

    return settings.get(
        "upload_mode",
        "video"
    )


# =========================
# THUMBNAIL
# =========================

def get_thumbnail():

    # First check environment variable
    thumb_file_id = os.getenv(
        "THUMB_FILE_ID",
        ""
    ).strip()

    if thumb_file_id:

        return thumb_file_id

    # Then check thumbnail.json
    try:

        if os.path.exists(
            THUMB_SETTINGS_FILE
        ):

            with open(
                THUMB_SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            thumbnail = data.get(
                "thumbnail"
            )

            if thumbnail:

                if os.path.exists(
                    thumbnail
                ):

                    return thumbnail

    except Exception as e:

        print(
            "Thumbnail settings error:",
            e
        )

    # Finally local default thumbnail
    if os.path.exists(
        THUMB_FILE
    ):

        return THUMB_FILE

    return None


# =========================
# CLEANUP USER
# =========================

def cleanup_user(
    user_id
):

    data = user_files.pop(
        user_id,
        None
    )

    if not data:
        return

    safe_remove(
        data.get(
            "file_path"
        )
    )

    safe_remove(
        data.get(
            "output_file"
        )
    )


# =========================
# DOWNLOAD PROGRESS
# =========================

async def update_download_progress(
    message,
    current,
    total
):

    if not total:
        return

    percent = (
        current / total
    ) * 100

    now = time.monotonic()

    # Store progress information on message object
    if not hasattr(
        update_download_progress,
        "_cache"
    ):

        update_download_progress._cache = {}

    cache = (
        update_download_progress._cache
    )

    key = id(message)

    previous = cache.get(
        key
    )

    if previous is None:

        cache[key] = (
            current,
            now
        )

        previous_current = current
        elapsed_since = 0

    else:

        previous_current, previous_time = (
            previous
        )

        elapsed_since = (
            now - previous_time
        )

        cache[key] = (
            current,
            now
        )

    speed = format_speed(
        current,
        previous_current,
        elapsed_since
    )

    # Overall average speed
    start_data = getattr(
        update_download_progress,
        "_starts",
        {}
    )

    if not hasattr(
        update_download_progress,
        "_starts"
    ):

        update_download_progress._starts = {}

    if key not in start_data:

        start_data[key] = (
            current,
            now
        )

    start_current, start_time = (
        start_data[key]
    )

    total_elapsed = (
        now - start_time
    )

    if total_elapsed > 0:

        average_speed = (
            current - start_current
        ) / total_elapsed

    else:

        average_speed = 0

    if average_speed > 0:

        remaining = (
            total - current
        )

        eta_seconds = (
            remaining /
            average_speed
        )

        eta = format_time(
            eta_seconds
        )

    else:

        eta = "--:--"

    elapsed = format_time(
        total_elapsed
    )

    try:

        await message.edit_text(
            "📥 Downloading...\n\n"
            f"{percent:.1f}% | "
            f"{format_bytes(current)} / "
            f"{format_bytes(total)}\n"
            f"⚡ {speed}\n"
            f"⏳ ETA: {eta}\n"
            f"🕒 Elapsed: {elapsed}"
        )

    except Exception:
        pass


# =========================
# UPLOAD PROGRESS
# =========================

async def update_upload_progress(
    message,
    current,
    total,
    user_id,
    started_at
):

    if not total:
        return

    if user_id not in user_files:
        return

    data = user_files[user_id]

    if data.get(
        "cancelled"
    ):

        return

    percent = (
        current / total
    ) * 100

    elapsed_seconds = (
        time.monotonic()
        - started_at
    )

    if elapsed_seconds > 0:

        speed_bytes = (
            current /
            elapsed_seconds
        )

    else:

        speed_bytes = 0

    remaining = (
        total - current
    )

    if speed_bytes > 0:

        eta_seconds = (
            remaining /
            speed_bytes
        )

        eta = format_time(
            eta_seconds
        )

    else:

        eta = "--:--"

    elapsed = format_time(
        elapsed_seconds
    )

    try:

        await message.edit_text(
            "📤 Uploading...\n\n"
            f"{percent:.1f}% | "
            f"{format_bytes(current)} / "
            f"{format_bytes(total)}\n"
            f"⚡ {format_bytes(speed_bytes)}/s\n"
            f"⏳ ETA: {eta}\n"
            f"🕒 Elapsed: {elapsed}"
        )

    except Exception:
        pass


# =========================
# DOWNLOAD FILE
# =========================

async def download_file(
    message,
    status,
    user_id,
    file_name,
    file_size
):

    started_at = time.monotonic()

    async def progress(
        current,
        total
    ):

        if user_id not in user_files:
            return

        if user_files[user_id].get(
            "cancelled"
        ):

            return

        await update_download_progress(
            status,
            current,
            total
        )

    try:

        destination = str(
            Path(DOWNLOAD_DIR)
            / safe_filename(file_name)
        )

        downloaded = await message.download(
            file_name=destination,
            progress=progress
        )

        return downloaded

    except Exception as e:

        print(
            "Download failed:",
            e
        )

        raise


# =========================
# UPLOAD FILE
# =========================

async def upload_file(
    client,
    message,
    file_path,
    status,
    user_id
):

    if not os.path.exists(
        file_path
    ):

        return False

    total = os.path.getsize(
        file_path
    )

    started_at = time.monotonic()

    async def progress(
        current,
        total_size
    ):

        await update_upload_progress(
            status,
            current,
            total_size,
            user_id,
            started_at
        )

    thumbnail = get_thumbnail()

    caption = (
        f"📁 {Path(file_path).name}"
    )

    try:

        upload_mode = get_upload_mode()

        if upload_mode == "document":

            kwargs = {
                "document": file_path,
                "caption": caption,
                "progress": progress
            }

            if thumbnail and os.path.exists(
                thumbnail
            ):

                kwargs["thumb"] = thumbnail

            await message.reply_document(
                **kwargs
            )

        else:

            kwargs = {
                "video": file_path,
                "caption": caption,
                "supports_streaming": True,
                "progress": progress
            }

            if thumbnail and os.path.exists(
                thumbnail
            ):

                kwargs["thumb"] = thumbnail

            await message.reply_video(
                **kwargs
            )

        return True

    except Exception as e:

        print(
            "Upload failed:",
            e
        )

        return False
        # =========================
# THUMBNAIL COMMAND
# =========================

@Client.on_message(
    filters.command("setthumb")
    & filters.private
)
async def set_thumb_command(
    client,
    message
):

    if message.from_user.id != OWNER_ID:

        await message.reply_text(
            "❌ This command is only for owner."
        )

        return

    if not message.reply_to_message:

        await message.reply_text(
            "📸 Reply to a photo with /setthumb"
        )

        return

    replied = message.reply_to_message

    if not replied.photo:

        await message.reply_text(
            "❌ Please reply to a photo."
        )

        return

    status = await message.reply_text(
        "⏳ Saving permanent thumbnail..."
    )

    try:

        downloaded = await replied.download(
            file_name=THUMB_FILE
        )

        if not downloaded or not os.path.exists(
            downloaded
        ):

            await status.edit_text(
                "❌ Failed to save thumbnail."
            )

            return

        with open(
            THUMB_SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "thumbnail": THUMB_FILE
                },
                f,
                indent=2
            )

        await status.edit_text(
            "✅ Permanent thumbnail saved.\n\n"
            "It will be used for compressed videos."
        )

    except Exception as e:

        print(
            "Set thumbnail error:",
            e
        )

        await status.edit_text(
            f"❌ Thumbnail save failed:\n`{e}`"
        )


# =========================
# FILE HANDLER
# =========================

@Client.on_message(
    filters.private
    & (
        filters.document
        | filters.video
        | filters.audio
        | filters.voice
        | filters.animation
    )
)
async def file_handler(
    client,
    message
):

    user_id = message.from_user.id

    # Prevent multiple active files
    if user_id in user_files:

        current = user_files[user_id]

        active_task = current.get(
            "task"
        )

        if active_task and not active_task.done():

            await message.reply_text(
                "⚠️ You already have a file processing.\n\n"
                "Please wait or use /cancel."
            )

            return

    media = (
        message.document
        or message.video
        or message.audio
        or message.voice
        or message.animation
    )

    if not media:
        return

    original_name = getattr(
        media,
        "file_name",
        None
    )

    if not original_name:

        if message.video:
            original_name = "video.mp4"

        elif message.animation:
            original_name = "animation.mp4"

        elif message.audio:
            original_name = "audio"

        elif message.voice:
            original_name = "voice.ogg"

        else:
            original_name = "file"

    original_name = safe_filename(
        original_name
    )

    file_size = getattr(
        media,
        "file_size",
        0
    ) or 0

    status = await message.reply_text(
        "📥 Downloading...\n\n"
        "0.0% | 0 B/s | ETA: --:-- | Elapsed: 00:00"
    )

    user_files[user_id] = {
        "message": message,
        "file_path": None,
        "output_file": None,
        "process": None,
        "cancelled": False,
        "status_message": status,
        "task": None,
        "original_name": original_name,
        "file_size": file_size,
        "waiting_name": False,
        "new_name": None
    }

    try:

        downloaded = await download_file(
            message,
            status,
            user_id,
            original_name,
            file_size
        )

        if user_id not in user_files:

            safe_remove(
                downloaded
            )

            return

        data = user_files[user_id]

        if data.get("cancelled"):

            safe_remove(
                downloaded
            )

            try:

                await status.edit_text(
                    "❌ Download cancelled."
                )

            except Exception:
                pass

            cleanup_user(
                user_id
            )

            return

        data["file_path"] = str(
            downloaded
        )

        await status.edit_text(
            "📥 Download complete.\n\n"
            "✏️ Choose an action:"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✏️ Rename",
                        callback_data="rename_file"
                    ),
                    InlineKeyboardButton(
                        "🎬 Compress",
                        callback_data="compress_file"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="cancel_job"
                    )
                ]
            ]
        )

        await status.edit_reply_markup(
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            "File handler error:",
            e
        )

        if user_id in user_files:

            try:

                await status.edit_text(
                    f"❌ Download failed:\n`{str(e)[:1500]}`"
                )

            except Exception:
                pass

            cleanup_user(
                user_id
            )

        else:

            try:

                await status.edit_text(
                    f"❌ Error:\n`{str(e)[:1500]}`"
                )

            except Exception:
                pass


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

    if user_id not in user_files:

        await message.reply_text(
            "ℹ️ No active job found."
        )

        return

    data = user_files[user_id]

    data["cancelled"] = True

    process = data.get(
        "process"
    )

    if process:

        try:

            if process.returncode is None:

                process.kill()

        except Exception as e:

            print(
                "Process kill error:",
                e
            )

    task = data.get(
        "task"
    )

    if task:

        current_task = asyncio.current_task()

        if task is not current_task:

            if not task.done():

                task.cancel()

    status = data.get(
        "status_message"
    )

    if status:

        try:

            await status.edit_text(
                "❌ Operation cancelled."
            )

        except Exception:
            pass


# =========================
# RENAME NAME HANDLER
# =========================

@Client.on_message(
    filters.private
    & filters.text
    & ~filters.command("cancel")
)
async def get_new_name(
    client,
    message
):

    user_id = message.from_user.id

    if user_id not in user_files:
        return

    data = user_files[user_id]

    if not data.get(
        "waiting_name"
    ):

        return

    new_name = message.text.strip()

    if not new_name:

        await message.reply_text(
            "❌ Please enter a valid name."
        )

        return

    data["waiting_name"] = False
    data["new_name"] = new_name

    status = data.get(
        "status_message"
    )

    try:

        await status.edit_text(
            "✏️ Renaming..."
        )

    except Exception:
        pass

    input_file = data.get(
        "file_path"
    )

    if not input_file or not os.path.exists(
        input_file
    ):

        try:

            await status.edit_text(
                "❌ Source file not found."
            )

        except Exception:
            pass

        cleanup_user(
            user_id
        )

        return

    clean_name = safe_filename(
        new_name
    )

    # Preserve original extension if
    # user did not provide one.
    if not Path(
        clean_name
    ).suffix:

        original_suffix = Path(
            data.get(
                "original_name",
                ""
            )
        ).suffix

        if original_suffix:

            clean_name += original_suffix

    output_file = str(
        Path(DOWNLOAD_DIR)
        / clean_name
    )

    # Avoid input/output collision
    if os.path.abspath(
        output_file
    ) == os.path.abspath(
        input_file
    ):

        stem = Path(
            clean_name
        ).stem

        suffix = Path(
            clean_name
        ).suffix

        output_file = str(
            Path(DOWNLOAD_DIR)
            / f"{stem}_renamed{suffix}"
        )

    data["output_file"] = output_file

    # Video/animation gets FFmpeg remux
    is_video = bool(
        data["message"].video
        or data["message"].animation
    )

    try:

        if is_video:

            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                input_file,
                "-map",
                "0",
                "-map_metadata",
                "0",
                "-c",
                "copy",
                "-metadata",
                f"comment={PERMANENT_METADATA}",
                "-y",
                output_file
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:

                error = (
                    result.stderr.strip()
                    or "FFmpeg rename failed."
                )

                raise RuntimeError(
                    error
                )

        else:

            os.replace(
                input_file,
                output_file
            )

        if not os.path.exists(
            output_file
        ):

            raise RuntimeError(
                "Renamed file was not created."
            )

        await status.edit_text(
            "📤 Uploading renamed file...\n\n"
            "0.0% | 0 B/s | ETA: --:-- | Elapsed: 00:00"
        )

        success = await upload_file(
            client,
            data["message"],
            output_file,
            status,
            user_id
        )

        if data.get(
            "cancelled"
        ):

            try:

                await status.edit_text(
                    "❌ Operation cancelled."
                )

            except Exception:
                pass

            return

        if success:

            try:

                await status.edit_text(
                    "✅ Renamed file uploaded successfully."
                )

            except Exception:
                pass

        else:

            try:

                await status.edit_text(
                    "❌ Upload failed."
                )

            except Exception:
                pass

    except Exception as e:

        print(
            "Rename error:",
            e
        )

        try:

            await status.edit_text(
                f"❌ Rename failed:\n`{str(e)[:1500]}`"
            )

        except Exception:
            pass

    finally:

        cleanup_user(
            user_id
        )


# =========================
# VIDEO HEIGHT
# =========================

async def get_video_height(
    file_path
):

    try:

        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            return None

        value = result.stdout.strip()

        if not value:

            return None

        return int(
            value
        )

    except Exception as e:

        print(
            "Video height error:",
            e
        )

        return None


# =========================
# VIDEO DURATION
# =========================

async def get_duration(
    file_path
):

    try:

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            return 0

        value = result.stdout.strip()

        if not value:

            return 0

        return float(
            value
        )

    except Exception as e:

        print(
            "Duration error:",
            e
        )

        return 0
        # =========================
# CALLBACK HANDLER
# =========================

@Client.on_callback_query(
    filters.regex(
        r"^(rename_file|compress_file|cancel_job|compress_\d+)$"
    )
)
async def callback_handler(
    client,
    query
):

    user_id = query.from_user.id

    if user_id not in user_files:

        await query.answer(
            "No active file found.",
            show_alert=True
        )

        return

    data = user_files[user_id]

    action = query.data

    # =========================
    # CANCEL
    # =========================

    if action == "cancel_job":

        data["cancelled"] = True

        process = data.get(
            "process"
        )

        if process:

            try:

                if process.returncode is None:

                    process.kill()

            except Exception as e:

                print(
                    "Callback process kill error:",
                    e
                )

        task = data.get(
            "task"
        )

        if task:

            current_task = (
                asyncio.current_task()
            )

            if task is not current_task:

                if not task.done():

                    task.cancel()

        await query.answer(
            "Cancelled"
        )

        status = data.get(
            "status_message"
        )

        if status:

            try:

                await status.edit_text(
                    "❌ Operation cancelled."
                )

            except Exception:
                pass

        return

    # =========================
    # RENAME
    # =========================

    if action == "rename_file":

        data["waiting_name"] = True

        await query.answer()

        status = data.get(
            "status_message"
        )

        try:

            await status.edit_text(
                "✏️ Send the new file name.\n\n"
                "Example:\n"
                "`My Movie.mp4`",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Cancel",
                                callback_data="cancel_job"
                            )
                        ]
                    ]
                )
            )

        except Exception:
            pass

        return

    # =========================
    # COMPRESS MENU
    # =========================

    if action == "compress_file":

        input_file = data.get(
            "file_path"
        )

        if not input_file or not os.path.exists(
            input_file
        ):

            await query.answer(
                "Source file not found.",
                show_alert=True
            )

            cleanup_user(
                user_id
            )

            return

        # Compression is only for video
        if not (
            data["message"].video
            or data["message"].animation
            or data["message"].document
        ):

            await query.answer(
                "This file cannot be compressed.",
                show_alert=True
            )

            return

        height = await get_video_height(
            input_file
        )

        if not height:

            await query.answer(
                "Could not detect video resolution.",
                show_alert=True
            )

            return

        # Available quality options
        qualities = [
            360,
            480,
            720,
            1080
        ]

        # Never upscale
        qualities = [
            q
            for q in qualities
            if q <= height
        ]

        if not qualities:

            await query.answer(
                "Video is below 360p.",
                show_alert=True
            )

            return

        buttons = []

        row = []

        for quality in qualities:

            row.append(
                InlineKeyboardButton(
                    f"🎬 {quality}p",
                    callback_data=(
                        f"compress_{quality}"
                    )
                )
            )

            if len(row) == 2:

                buttons.append(
                    row
                )

                row = []

        if row:

            buttons.append(
                row
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cancel_job"
                )
            ]
        )

        status = data.get(
            "status_message"
        )

        try:

            await status.edit_text(
                f"🎬 Source resolution: {height}p\n\n"
                "Select compression quality:",
                reply_markup=InlineKeyboardMarkup(
                    buttons
                )
            )

        except Exception:
            pass

        await query.answer()

        return

    # =========================
    # QUALITY
    # =========================

    if action.startswith(
        "compress_"
    ):

        try:

            quality = int(
                action.split(
                    "_",
                    1
                )[1]
            )

        except Exception:

            await query.answer(
                "Invalid quality.",
                show_alert=True
            )

            return

        await start_compression(
            client,
            query,
            user_id,
            quality
        )

        return


# =========================
# START COMPRESSION
# =========================

async def start_compression(
    client,
    query,
    user_id,
    quality
):

    if user_id not in user_files:

        await query.answer(
            "No active file found.",
            show_alert=True
        )

        return

    data = user_files[user_id]

    input_file = data.get(
        "file_path"
    )

    if not input_file or not os.path.exists(
        input_file
    ):

        await query.answer(
            "Source file not found.",
            show_alert=True
        )

        cleanup_user(
            user_id
        )

        return

    # Supported resolutions only
    if quality not in (
        360,
        480,
        720,
        1080
    ):

        await query.answer(
            "Invalid quality.",
            show_alert=True
        )

        return

    # Check source resolution again
    source_height = await get_video_height(
        input_file
    )

    if not source_height:

        await query.answer(
            "Could not detect source resolution.",
            show_alert=True
        )

        return

    # Never allow upscaling
    if quality > source_height:

        await query.answer(
            f"Source video is only {source_height}p.",
            show_alert=True
        )

        return

    # Check duplicate task
    existing_task = data.get(
        "task"
    )

    if existing_task and not existing_task.done():

        await query.answer(
            "This file is already processing.",
            show_alert=True
        )

        return

    settings = load_compress_settings()

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

    upload_mode = get_upload_mode()

    original_name = data.get(
        "original_name",
        "video.mp4"
    )

    original_stem = Path(
        original_name
    ).stem

    output_name = safe_filename(
        f"{original_stem}_{quality}p.mp4"
    )

    output_file = str(
        Path(DOWNLOAD_DIR)
        / output_name
    )

    # Avoid collision between users/files
    if os.path.exists(
        output_file
    ):

        output_file = str(
            Path(DOWNLOAD_DIR)
            / (
                f"{original_stem}_"
                f"{quality}p_"
                f"{user_id}.mp4"
            )
        )

    data["output_file"] = (
        output_file
    )

    data["cancelled"] = False
    data["process"] = None

    await query.answer(
        "Compression started."
    )

    status = data.get(
        "status_message"
    )

    try:

        await status.edit_text(
            f"🎬 Preparing {quality}p compression...\n\n"
            "⏳ Waiting for encoder..."
        )

    except Exception:
        pass

    task = asyncio.create_task(
        compression_task(
            client=client,
            user_id=user_id,
            quality=quality,
            input_file=input_file,
            output_file=output_file,
            vcodec=vcodec,
            crf=crf,
            pix_fmt=pix_fmt,
            upload_mode=upload_mode
        )
    )

    data["task"] = task
    # =========================
# COMPRESSION TASK
# =========================

async def compression_task(
    client,
    user_id,
    quality,
    input_file,
    output_file,
    vcodec,
    crf,
    pix_fmt,
    upload_mode
):

    if user_id not in user_files:
        return

    data = user_files[user_id]

    status = data.get(
        "status_message"
    )

    process = None

    try:

        # Only one FFmpeg encoder at a time
        async with compression_lock:

            if user_id not in user_files:
                return

            data = user_files[user_id]

            if data.get(
                "cancelled"
            ):

                return

                        # Another job may have completed while
            # this task was waiting for the lock.
            if not os.path.exists(
                input_file
            ):

                raise RuntimeError(
                    "Input file not found."
                )

            data["status_message"] = status_msg

            # Get source duration
            duration = await get_duration(
                input_file
            )

            if duration <= 0:
                duration = 1

            data["duration"] = duration

            # Get compression settings
            settings = load_compress_settings()

            vcodec = settings.get(
                "vcodec",
                "libx264"
            )

            crf = str(
                settings.get(
                    "crf",
                    24
                )
            )

            pix_fmt = settings.get(
                "pix_fmt",
                "yuv420p"
            )

            # Get source video height
            source_height = await get_video_height(
                input_file
            )

            if source_height <= 0:
                raise RuntimeError(
                    "Could not detect video resolution."
                )

            # Never upscale the video
            if quality > source_height:
                quality = source_height

            output_file = str(
                Path(input_file).with_name(
                    f"{Path(input_file).stem}_{quality}p.mp4"
                )
            )

            data["output_file"] = output_file

            # Remove old output if exists
            safe_remove(
                output_file
            )

            await status_msg.edit_text(
                f"⚙️ **Starting Compression...**\n\n"
                f"🎞️ Quality: `{quality}p`\n"
                f"🎥 Codec: `{vcodec}`\n"
                f"🎚️ CRF: `{crf}`\n"
                f"📦 Format: `MP4`\n\n"
                f"⏳ Preparing FFmpeg..."
            )

            # FFmpeg command
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-stats_period",
                "1",

                "-i",
                input_file,

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
                crf,

                "-pix_fmt",
                pix_fmt,

                "-c:a",
                "aac",

                "-b:a",
                "96k",

                "-map_metadata",
                "0",

                "-metadata",
                f"comment={PERMANENT_METADATA}",

                "-movflags",
                "+faststart",

                "-y",
                output_file
            ]

            print(
                "Starting FFmpeg:",
                " ".join(command)
            )

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            data["process"] = process

            start_time = time.monotonic()

            last_update = 0

            current_seconds = 0.0
            speed_value = 0.0

            while True:

                # User cancelled
                if data.get(
                    "cancelled",
                    False
                ):

                    try:
                        process.kill()
                    except Exception:
                        pass

                    await process.wait()

                    safe_remove(
                        output_file
                    )

                    await status_msg.edit_text(
                        "❌ **Compression Cancelled**"
                    )

                    return

                line = await process.stdout.readline()

                if not line:
                    break

                line = line.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if "=" not in line:
                    continue

                key, value = line.split(
                    "=",
                    1
                )

                if key == "out_time_ms":

                    try:
                        current_seconds = (
                            int(value) / 1_000_000
                        )

                    except Exception:
                        current_seconds = 0

                elif key == "speed":

                    try:
                        speed_value = float(
                            value.replace("x", "")
                        )

                    except Exception:
                        speed_value = 0

                elif key == "progress" and value == "end":

                    current_seconds = duration

                now = time.monotonic()

                if (
                    now - last_update >= 2
                    or key == "progress"
                ):

                    last_update = now

                    percent = min(
                        100,
                        max(
                            0,
                            (current_seconds / duration) * 100
                        )
                    )

                    elapsed = (
                        now - start_time
                    )

                    if speed_value > 0:

                        remaining = max(
                            0,
                            duration - current_seconds
                        )

                        eta = (
                            remaining / speed_value
                        )

                    else:
                        eta = 0

                    await status_msg.edit_text(
                        "⚙️ **Compressing...**\n\n"
                        f"📊 `{percent:.1f}%`\n"
                        f"🚀 Speed: `{speed_value:.2f}x`\n"
                        f"⏱️ Elapsed: `{format_time(elapsed)}`\n"
                        f"⌛ ETA: `{format_time(eta)}`\n\n"
                        f"🎞️ Quality: `{quality}p`\n"
                        f"🎥 Codec: `{vcodec}`\n\n"
                        "❌ Press **Cancel** to stop."
                    )
                                # Wait for FFmpeg to finish
            await process.wait()

            data["process"] = None

            # Read FFmpeg error output
            stderr_output = await process.stderr.read()

            if data.get(
                "cancelled",
                False
            ):

                safe_remove(
                    output_file
                )

                await status_msg.edit_text(
                    "❌ **Compression Cancelled**"
                )

                return

            if process.returncode != 0:

                error_text = stderr_output.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                print(
                    "FFmpeg failed:",
                    error_text
                )

                safe_remove(
                    output_file
                )

                await status_msg.edit_text(
                    "❌ **Compression Failed**\n\n"
                    f"```text\n"
                    f"{error_text[-2500:] or 'Unknown FFmpeg error'}"
                    f"\n```"
                )

                return

            # Check output file
            if not os.path.exists(
                output_file
            ):

                raise RuntimeError(
                    "FFmpeg completed but output file was not created."
                )

            output_size = os.path.getsize(
                output_file
            )

            if output_size <= 0:

                raise RuntimeError(
                    "Compressed output file is empty."
                )

            print(
                "Compression completed:",
                output_file
            )

            # Upload starts
            await status_msg.edit_text(
                "📤 **Uploading...**\n\n"
                "📊 `0.0%`\n"
                "🚀 Speed: `0 B/s`\n"
                "⏱️ Elapsed: `0s`\n"
                "⌛ ETA: `--`"
            )

            upload_start = time.monotonic()

            upload_success = await upload_file(
                client,
                status_msg,
                output_file,
                data,
                upload_start
            )

            if data.get(
                "cancelled",
                False
            ):

                safe_remove(
                    output_file
                )

                return

            if not upload_success:

                safe_remove(
                    output_file
                )

                await status_msg.edit_text(
                    "❌ **Upload Failed**"
                )

                return

            # Upload completed successfully
            elapsed_total = (
                time.monotonic()
                - start_time
            )

            await status_msg.edit_text(
                "✅ **Completed Successfully!**\n\n"
                f"🎞️ Quality: `{quality}p`\n"
                f"📦 Size: `{format_bytes(output_size)}`\n"
                f"⏱️ Total Time: `{format_time(elapsed_total)}`"
            )

            # Remove temporary files
            safe_remove(
                input_file
            )

            safe_remove(
                output_file
            )
                    except asyncio.CancelledError:

            print(
                f"Compression task cancelled for user {user_id}"
            )

            process = data.get(
                "process"
            )

            if process:

                try:
                    process.kill()
                except Exception:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

            output_file = data.get(
                "output_file"
            )

            if output_file:
                safe_remove(
                    output_file
                )

            try:
                await status_msg.edit_text(
                    "❌ **Task Cancelled**"
                )
            except Exception:
                pass

            raise

        except Exception as e:

            print(
                f"Compression error for user {user_id}:",
                e
            )

            process = data.get(
                "process"
            )

            if process:

                try:
                    process.kill()
                except Exception:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

            output_file = data.get(
                "output_file"
            )

            if output_file:
                safe_remove(
                    output_file
                )

            try:

                await status_msg.edit_text(
                    "❌ **Something went wrong!**\n\n"
                    f"`{str(e)[:3000]}`"
                )

            except Exception:
                pass

        finally:

            data["process"] = None
            data["task"] = None

            # Keep cleanup outside the lock
            # so another queued job can continue.
            try:

                if user_files.get(
                    user_id
                ) is data:

                    cleanup_user(
                        user_id
                    )

            except Exception as e:

                print(
                    "Cleanup error:",
                    e
                )
                # ---------------------------------------------------------
# Rename / Compression Helpers
# ---------------------------------------------------------

async def rename_file(
    client,
    message,
    old_file,
    new_name,
    status_message
):

    try:

        new_name = safe_filename(
            new_name
        )

        if not new_name:
            raise ValueError(
                "Invalid file name."
            )

        extension = Path(
            old_file
        ).suffix

        if not Path(
            new_name
        ).suffix:

            new_name += extension

        output_file = str(
            Path(old_file).with_name(
                new_name
            )
        )

        safe_remove(
            output_file
        )

        await status_message.edit_text(
            "✏️ **Renaming...**"
        )

        # Video files are remuxed so metadata
        # and streams remain intact.
        if extension.lower() in [
            ".mp4",
            ".mkv",
            ".mov",
            ".webm",
            ".avi",
            ".m4v"
        ]:

            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                old_file,
                "-map",
                "0",
                "-map_metadata",
                "0",
                "-metadata",
                f"comment={PERMANENT_METADATA}",
                "-c",
                "copy",
                "-y",
                output_file
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if result.returncode != 0:

                error_text = result.stderr.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                raise RuntimeError(
                    error_text[-2000:]
                    or "FFmpeg rename failed."
                )

            safe_remove(
                old_file
            )

        else:

            # For non-video files, simply rename.
            os.replace(
                old_file,
                output_file
            )

        await status_message.edit_text(
            "📤 **Uploading renamed file...**"
        )

        upload_start = time.monotonic()

                data = {
            "message": message,
            "file_path": output_file,
            "output_file": output_file,
            "cancelled": False,
            "status_message": status_message,
            "original_name": Path(
                old_file
            ).name,
            "new_name": new_name
        }

        success = await upload_file(
            client,
            status_message,
            output_file,
            data,
            upload_start
        )

        if not success:
            raise RuntimeError(
                "Upload failed."
            )

        safe_remove(
            output_file
        )

        try:
            await status_message.edit_text(
                "✅ **Rename Completed!**"
            )
        except Exception:
            pass

        return True

    except Exception as e:

        print(
            "Rename error:",
            e
        )

        safe_remove(
            output_file
            if "output_file" in locals()
            else None
        )

        try:
            await status_message.edit_text(
                "❌ **Rename Failed**\n\n"
                f"`{str(e)[:2500]}`"
            )
        except Exception:
            pass

        return False


async def process_rename(
    client,
    message,
    new_name
):

    user_id = message.from_user.id

    data = user_files.get(
        user_id
    )

    if not data:
        return

    old_file = data.get(
        "file_path"
    )

    status_message = data.get(
        "status_message"
    )

    if not old_file or not os.path.exists(
        old_file
    ):

        try:
            await message.reply_text(
                "❌ File not found."
            )
        except Exception:
            pass

        cleanup_user(
            user_id
        )

        return

    data["waiting_name"] = False
    data["new_name"] = new_name

    await rename_file(
        client,
        message,
        old_file,
        new_name,
        status_message
    )

    cleanup_user(
        user_id
    )
# ---------------------------------------------------------
# New Name Message Handler
# ---------------------------------------------------------

@app.on_message(
    filters.private
    & filters.text
    & ~filters.command(
        ["start", "cancel", "setthumb"]
    ),
    group=20
)
async def new_name_handler(
    client,
    message
):

    user_id = message.from_user.id

    data = user_files.get(
        user_id
    )

    if not data:
        return

    # Only handle messages when the bot
    # is waiting for a new file name.
    if not data.get(
        "waiting_name",
        False
    ):
        return

    new_name = message.text.strip()

    if not new_name:
        await message.reply_text(
            "❌ Please send a valid file name."
        )
        return

    if new_name.startswith("/"):
        return

    data["waiting_name"] = False

    try:

        await process_rename(
            client,
            message,
            new_name
        )

    except Exception as e:

        print(
            "Rename handler error:",
            e
        )

        try:
            await message.reply_text(
                "❌ **Rename Failed**\n\n"
                f"`{str(e)[:2000]}`"
            )
        except Exception:
            pass

        cleanup_user(
            user_id
        )


# ---------------------------------------------------------
# Safety Cleanup
# ---------------------------------------------------------

async def cleanup_on_shutdown():

    for user_id in list(
        user_files.keys()
    ):

        try:

            data = user_files.get(
                user_id
            )

            if not data:
                continue

            process = data.get(
                "process"
            )

            if process:

                try:
                    process.kill()
                except Exception:
                    pass

            cleanup_user(
                user_id
            )

        except Exception as e:

            print(
                "Shutdown cleanup error:",
                e
            )


print(
    "✅ Rename + Compression plugin loaded successfully."
)
