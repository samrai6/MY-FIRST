from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters

from pathlib import Path
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
            data = json.load(f)

        data.setdefault("vcodec", "libx264")
        data.setdefault("crf", 24)
        data.setdefault("pix_fmt", "yuv420p")
        data.setdefault("upload_mode", "video")

        return data

    except Exception:

        return {
            "vcodec": "libx264",
            "crf": 24,
            "pix_fmt": "yuv420p",
            "upload_mode": "video"
        }


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

    with open(THUMB_SETTINGS_FILE, "w") as f:
        json.dump(
            {"file_id": file_id},
            f
        )


async def get_thumbnail(client):

    file_id = load_thumbnail_file_id()

    if not file_id:
        return None

    try:

        if os.path.exists(THUMB_FILE):
            return THUMB_FILE

        Path(DOWNLOAD_DIR).mkdir(
            parents=True,
            exist_ok=True
        )

        return await client.download_media(
            file_id,
            file_name=THUMB_FILE
        )

    except Exception:

        return None


# =========================
# DIRECTORY
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

        await message.download(
            file_name=THUMB_FILE
        )

    except Exception:
        pass

    await message.reply_text(
        "✅ Thumbnail saved successfully!\n\n"
        "🎬 Video + 📄 Document\n"
        "🖼 This thumbnail will be used automatically."
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
# GET NAME
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

    old_file = Path(file_path)

    # =========================
    # EXTENSION FIX
    # =========================

    if Path(new_name).suffix:

        final_name = new_name

    else:

        final_name = new_name + old_file.suffix

    new_file = old_file.with_name(
        final_name
    )

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

        return

    user_files[uid]["file_path"] = str(
        new_file
    )

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


    # =========================
    # CANCEL
    # =========================

    if query.data == "cancel_compress":

        data = user_files.get(uid)

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

            except Exception:
                pass

        try:

            await query.message.edit_text(
                "🛑 Cancelling compression..."
            )

        except Exception:
            pass

        return


    # =========================
    # RENAME ONLY
    # =========================

    if query.data == "rename_only":

        file_path = user_files[uid].get(
            "file_path"
        )

        if not file_path or not os.path.exists(file_path):

            await query.message.reply_text(
                "❌ File not found."
            )

            return

        thumbnail = await get_thumbnail(
            client
        )

        try:

            if thumbnail:

                try:

                    await query.message.reply_document(
                        document=file_path,
                        thumb=thumbnail
                    )

                except Exception:

                    await query.message.reply_document(
                        document=file_path
                    )

            else:

                await query.message.reply_document(
                    document=file_path
                )

        except Exception as e:

            await query.message.reply_text(
                f"❌ Upload failed.\n\n{e}"
            )

            return

        try:

            if os.path.exists(file_path):
                os.remove(file_path)

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
    # COMPRESS
    # =========================

    if query.data.startswith("compress_"):

        quality = query.data.split(
            "_",
            1
        )[1]

        input_path = Path(
            user_files[uid]["file_path"]
        )

        if not input_path.exists():

            await query.message.reply_text(
                "❌ Input file not found."
            )

            return

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p{input_path.suffix}"
        )

        settings = load_compress_settings()


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


        # =========================
        # STATUS
        # =========================

        status = await query.message.reply_text(

            "🗜 Compressing...\n\n"
            "📊 Progress: 0%\n"
            "⏱ Elapsed: 0s",

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

        except Exception as e:

            await status.edit_text(
                f"❌ FFmpeg failed to start.\n\n{e}"
            )

            return


        start = time.time()

        last_percent = -1
        last_update = 0


        # =========================
        # PROGRESS
        # =========================

        while True:

            line = await process.stdout.readline()

            if not line:
                break

            if user_files.get(uid, {}).get(
                "cancelled"
            ):

                break

            line = line.decode(
                errors="ignore"
            ).strip()

            if not line.startswith(
                "out_time_ms="
            ):
                continue

            value = line.split(
                "=",
                1
            )[1]

            if value == "N/A":
                continue

            try:

                current = int(
                    value
                ) / 1000000

            except ValueError:

                continue

            percent = min(
                int(
                    (current / duration) * 100
                ),
                100
            )

            elapsed = int(
                time.time() - start
            )

            now = time.time()


            # =========================
            # UPDATE STATUS
            # =========================

            if (
                percent != last_percent
                and
                (
                    now - last_update >= 1
                    or percent >= 100
                )
            ):

                try:

                    await status.edit_text(

                        f"🗜 Compressing {quality}p...\n\n"

                        f"📊 Progress: {percent}%\n"

                        f"⏱ Elapsed: {elapsed}s",

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

                    last_percent = percent
                    last_update = now

                except Exception:
                    pass


        # =========================
        # CANCELLED
        # =========================

        if user_files.get(uid, {}).get(
            "cancelled"
        ):

            try:

                if process.returncode is None:

                    process.kill()

                await process.wait()

            except Exception:
                pass

            try:

                if output_file.exists():
                    output_file.unlink()

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

            try:

                await status.edit_text(
                    "❌ Compression Cancelled"
                )

            except Exception:
                pass

            return


        # =========================
        # WAIT
        # =========================

        stderr_data = await process.stderr.read()

        return_code = await process.wait()

        elapsed = int(
            time.time() - start
        )

        user_files[uid]["process"] = None


        # =========================
        # FAILED
        # =========================

        if return_code != 0:

            error_text = stderr_data.decode(
                errors="ignore"
            ).strip()

            if len(error_text) > 1000:
                error_text = error_text[-1000:]

            await status.edit_text(

                "❌ Compression Failed\n\n"
                f"{error_text}"
            )

            try:

                if output_file.exists():
                    output_file.unlink()

            except Exception:
                pass

            return


        # =========================
        # OUTPUT CHECK
        # =========================

        if not output_file.exists():

            await status.edit_text(
                "❌ Compression failed: output file not found."
            )

            return


        user_files[uid]["output_file"] = str(
            output_file
        )


        # =========================
        # UPLOAD
        # =========================

        upload_mode = settings.get(
            "upload_mode",
            "video"
        )

        thumbnail = await get_thumbnail(
            client
        )


        try:

            await status.edit_text(

                f"✅ Compression Done\n\n"

                f"🎬 Quality: {quality}p\n"

                f"⏱ Time: {elapsed}s\n\n"

                f"📤 Uploading..."
            )

        except Exception:
            pass


        # =========================
        # VIDEO
        # =========================

        if upload_mode == "video":

            try:

                if thumbnail:

                    try:

                        await query.message.reply_video(
                            video=str(output_file),
                            thumb=thumbnail
                        )

                    except Exception:

                        await query.message.reply_video(
                            video=str(output_file)
                        )

                else:

                    await query.message.reply_video(
                        video=str(output_file)
                    )

            except Exception as e:

                await status.edit_text(
                    f"❌ Video upload failed.\n\n{e}"
                )

                return


        # =========================
        # DOCUMENT
        # =========================

        else:

            try:

                if thumbnail:

                    try:

                        await query.message.reply_document(
                            document=str(output_file),
                            thumb=thumbnail
                        )

                    except Exception:

                        await query.message.reply_document(
                            document=str(output_file)
                        )

                else:

                    await query.message.reply_document(
                        document=str(output_file)
                    )

            except Exception as e:

                await status.edit_text(
                    f"❌ Document upload failed.\n\n{e}"
                )

                return


        # =========================
        # FINAL
        # =========================

        try:

            await status.edit_text(
                f"✅ Done • {quality}p • {elapsed}s"
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
