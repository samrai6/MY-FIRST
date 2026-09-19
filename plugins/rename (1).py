from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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

    except Exception as e:

        print(
            "Thumbnail download error:",
            e
        )

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

                except Exception as e:

                    print(
                        "Video thumbnail upload failed:",
                        e
                    )

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

        except Exception as e:

            print(
                "Video upload failed:",
                e
            )

            try:

                await message.reply_document(
                    document=str(file_path),
                    caption=caption
                )

                return True

            except Exception as e2:

                print(
                    "Document fallback failed:",
                    e2
                )

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

            except Exception as e:

                print(
                    "Document thumbnail failed:",
                    e
                )

        await message.reply_document(
            document=str(file_path),
            caption=caption
        )

        return True

    except Exception as e:

        print(
            "Document upload failed:",
            e
        )

        return False


# =========================
# SET THUMB
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
    filters.photo
    & filters.private
)
async def save_thumbnail(
    client,
    message
):

    if message.from_user.id != OWNER_ID:
        return

    file_id = message.photo.file_id

    save_thumbnail_file_id(
        file_id
    )

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

        if not (
            downloaded
            and os.path.exists(THUMB_FILE)
        ):

            print(
                "Thumbnail local save failed."
            )

    except Exception as e:

        print(
            "Thumbnail download error:",
            e
        )

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
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.animation
)
async def file_handler(
    client,
    message
):

    user_files[
        message.from_user.id
    ] = {

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
# NEW NAME
# =========================

@Client.on_message(
    filters.text
    & ~filters.command("start")
    & ~filters.command("setthumb")
    & ~filters.command("setting")
    & ~filters.command("settings")
)
async def get_new_name(
    client,
    message
):

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

        user_files.pop(
            uid,
            None
        )

        return

    old_file = Path(
        file_path
    )

    # =========================
    # EXTENSION
    # =========================

    if Path(new_name).suffix:

        final_name = new_name

    else:

        final_name = (
            new_name
            + old_file.suffix
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

            old_file.rename(
                new_file
            )

    except Exception as e:

        await message.reply_text(
            f"❌ Rename failed.\n\n{e}"
        )

        try:

            if old_file.exists():
                old_file.unlink()

        except Exception:
            pass

        user_files.pop(
            uid,
            None
        )

        return

    user_files[uid]["file_path"] = str(
        new_file
    )

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
# CALLBACK HANDLER
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

    # =========================
    # CANCEL
    # =========================

    if query.data == "cancel_compress":

        await query.answer(
            "Cancelling..."
        )

        data = user_files.get(
            uid
        )

        if not data:
            return

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

        try:

            await query.message.edit_text(
                "🛑 Cancelling compression..."
            )

        except Exception:
            pass

        return

    await query.answer()

    # =========================
    # RENAME ONLY
    # =========================

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

        source = Path(
            file_path
        )

        upload_mode = get_upload_mode()

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

        thumbnail = await get_thumbnail(
            client
        )

        video_extensions = (
            ".mp4",
            ".mkv",
            ".mov",
            ".avi",
            ".webm",
            ".m4v",
            ".ts"
        )

        # =========================
        # METADATA REMUX
        # =========================

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

                    if result.stderr:

                        print(
                            "Metadata warning:",
                            result.stderr.decode(
                                "utf-8",
                                errors="ignore"
                            )
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

        # =========================
        # UPLOAD
        # =========================

        success = await upload_file(
            client,
            query.message,
            source,
            thumbnail
        )

        if not success:

            await query.message.reply_text(
                "❌ Upload failed."
            )

            return

        # =========================
        # CLEANUP
        # =========================

        try:

            if source.exists():
                source.unlink()

        except Exception:
            pass

        user_files.pop(
            uid,
            None
        )

        return


# =========================
# COMPRESS MENU
# =========================

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
      # =========================
# COMPRESSION
# =========================

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

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p.mp4"
        )

        user_files[uid]["output_file"] = str(
            output_file
        )

        try:

            if output_file.exists():
                output_file.unlink()

        except Exception:
            pass

        # =========================
        # LOAD SETTINGS
        # =========================

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

        # =========================
        # VIDEO DURATION
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

        except Exception as e:

            await query.message.reply_text(
                f"❌ Unable to read video duration.\n\n{e}"
            )

            return

        if duration <= 0:
            duration = 1

        # =========================
        # FFMPEG COMMAND
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

            "-map_metadata",
            "0",

            "-metadata",
            f"comment={PERMANENT_METADATA}",

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
            "📊 Progress: 0%\n"
            "⏱ Elapsed: 0s\n\n"
            "Please wait...",

            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🛑 Cancel",
                            callback_data="cancel_compress"
                        )
                    ]
                ]
            )
        )

        user_files[uid]["process"] = None

        start_time = time.time()

        # =========================
        # START FFMPEG
        # =========================

        try:

            process = await asyncio.create_subprocess_exec(

                *cmd,

                stdout=asyncio.subprocess.PIPE,

                stderr=asyncio.subprocess.PIPE
            )

            user_files[uid]["process"] = process

            last_update = 0
            last_percent = -1

            # =========================
            # PROGRESS LOOP
            # =========================

            while True:

                if user_files[uid].get("cancelled"):

                    try:

                        if process.returncode is None:
                            process.kill()

                    except Exception:
                        pass

                    break

                line = await process.stdout.readline()

                if not line:

                    if process.returncode is not None:
                        break

                    await asyncio.sleep(
                        0.1
                    )

                    continue

                line = line.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if line.startswith("out_time_ms="):

                    try:

                        out_time_ms = int(
                            line.split(
                                "=",
                                1
                            )[1]
                        )

                        current_time = (
                            out_time_ms / 1000000
                        )

                        percent = int(

                            min(
                                100,
                                (
                                    current_time
                                    / duration
                                ) * 100
                            )

                        )

                        elapsed = int(
                            time.time()
                            - start_time
                        )

                        now = time.time()

                        # =========================
                        # UPDATE EVERY 3 SECONDS
                        # =========================

                        if (

                            percent != last_percent

                            and (
                                now - last_update >= 3
                                or percent >= 100
                            )

                        ):

                            try:

                                await status.edit_text(

                                    "🗜 Compressing...\n\n"
                                    f"🎬 Quality: {quality}p\n"
                                    f"🎞 Codec: {vcodec}\n"
                                    f"🎚 CRF: {crf}\n"
                                    f"📊 Progress: {percent}%\n"
                                    f"⏱ Elapsed: {elapsed}s\n\n"
                                    "Please wait...",

                                    reply_markup=InlineKeyboardMarkup(
                                        [
                                            [
                                                InlineKeyboardButton(
                                                    "🛑 Cancel",
                                                    callback_data="cancel_compress"
                                                )
                                            ]
                                        ]
                                    )
                                )

                            except Exception:
                                pass

                            last_percent = percent
                            last_update = now

                    except Exception:
                        pass

            await process.wait()

            stderr_data = await process.stderr.read()

            error_text = stderr_data.decode(
                "utf-8",
                errors="ignore"
            ).strip()

            user_files[uid]["process"] = None

            # =========================
            # CANCELLED
            # =========================

            if user_files[uid].get("cancelled"):

                try:

                    if output_file.exists():
                        output_file.unlink()

                except Exception:
                    pass

                try:

                    await status.edit_text(
                        "🛑 Compression cancelled."
                    )

                except Exception:
                    pass

                try:

                    if input_path.exists():
                        input_path.unlink()

                except Exception:
                    pass

                user_files.pop(
                    uid,
                    None
                )

                return

            # =========================
            # FFMPEG ERROR
            # =========================

            if (

                process.returncode != 0
                or not output_file.exists()
                or output_file.stat().st_size == 0

            ):

                print(
                    "FFmpeg compression failed:",
                    error_text
                )

                try:

                    if output_file.exists():
                        output_file.unlink()

                except Exception:
                    pass

                try:

                    await status.edit_text(

                        "❌ Compression failed.\n\n"
                        + (
                            error_text[-1500:]
                            if error_text
                            else "Unknown FFmpeg error."
                        )

                    )

                except Exception:
                    pass

                return

            # =========================
            # UPLOAD
            # =========================

            try:

                await status.edit_text(

                    "✅ Compression completed!\n\n"
                    f"📄 `{output_file.name}`\n"
                    "📤 Uploading..."

                )

            except Exception:
                pass

            thumbnail = await get_thumbnail(
                client
            )

            success = await upload_file(

                client,
                status,
                output_file,
                thumbnail
            )

            if not success:

                try:

                    await status.edit_text(
                        "❌ Upload failed."
                    )

                except Exception:
                    pass

                return

            # =========================
            # DONE
            # =========================

            elapsed = int(
                time.time()
                - start_time
            )

            try:

                await status.edit_text(

                    "✅ Done!\n\n"
                    f"📄 `{output_file.name}`\n"
                    f"🎬 Quality: {quality}p\n"
                    f"🎞 Codec: {vcodec}\n"
                    f"🎚 CRF: {crf}\n"
                    f"⏱ Time: {elapsed}s\n"
                    f"🏷 Metadata: {PERMANENT_METADATA}"

                )

            except Exception:
                pass

            # =========================
            # CLEANUP
            # =========================

            try:

                if input_path.exists():
                    input_path.unlink()

            except Exception:
                pass

            try:

                if output_file.exists():
                    output_file.unlink()

            except Exception:
                pass

            user_files.pop(
                uid,
                None
            )

        # =========================
        # GENERAL ERROR
        # =========================

        except Exception as e:

            if uid in user_files:

                user_files[uid]["process"] = None

            try:

                if output_file.exists():
                    output_file.unlink()

            except Exception:
                pass

            print(
                "Compression exception:",
                repr(e)
            )

            try:

                await status.edit_text(

                    "❌ Compression error.\n\n"
                    f"{e}"

                )

            except Exception:
                pass  
