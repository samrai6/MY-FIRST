from pathlib import Path
import asyncio
import subprocess

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from config import DOWNLOAD_DIR
from .file_utils import safe_filename, get_extension
from .progress import make_download_callback, make_upload_callback
from .thumbnail import get_thumbnail
from .compress import compress_file
from .setting import load_settings
from .cancel import get_cancel_event, clear_cancel_event


PENDING_FILES = {}


MEDIA_EXTENSIONS = (
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".m4v"
)


def build_renamed_filename(original_name, new_name):
    original_ext = get_extension(original_name)

    new_name = safe_filename(
        new_name,
        default="file"
    )

    new_name = Path(new_name).stem

    if not new_name:
        new_name = "file"

    if original_ext:
        return new_name + original_ext

    return new_name


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


async def download_file(
    status,
    source_message
):

    callback = make_download_callback(
        status,
        action="⬇️ Downloading..."
    )

    return await source_message.download(
        file_name=DOWNLOAD_DIR,
        progress=callback
    )


async def upload_file(
    status,
    file_path,
    thumbnail=None
):

    file_path = Path(file_path)

    if not file_path.exists():
        return False

    callback = make_upload_callback(
        status,
        action="📤 Uploading..."
    )

    settings = load_settings()

    upload_mode = settings.get(
        "upload_mode",
        "video"
    )

    # ==============================
    # DOCUMENT MODE
    # ==============================

    if upload_mode == "document":

        try:

            kwargs = {
                "document": str(file_path),
                "progress": callback
            }

            if (
                thumbnail
                and Path(thumbnail).exists()
            ):
                kwargs["thumb"] = thumbnail

            await status.reply_document(
                **kwargs
            )

            return True

        except Exception as e:

            print(
                "Document upload failed:",
                e
            )

            return False

    # ==============================
    # VIDEO MODE
    # ==============================

    if file_path.suffix.lower() in MEDIA_EXTENSIONS:

        try:

            kwargs = {
                "video": str(file_path),
                "progress": callback
            }

            if (
                thumbnail
                and Path(thumbnail).exists()
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

    # ==============================
    # DOCUMENT FALLBACK
    # ==============================

    try:

        kwargs = {
            "document": str(file_path),
            "progress": callback
        }

        if (
            thumbnail
            and Path(thumbnail).exists()
        ):
            kwargs["thumb"] = thumbnail

        await status.reply_document(
            **kwargs
        )

        return True

    except Exception as e:

        print(
            "Document fallback failed:",
            e
        )

        return False


def action_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ Rename",
                    callback_data="fileaction_rename"
                ),
                InlineKeyboardButton(
                    "🗜️ Compress",
                    callback_data="fileaction_compress"
                )
            ]
        ]
    )


# =========================================================
# STEP 1 — RECEIVE FILE
# =========================================================

@Client.on_message(
    (
        filters.document
        | filters.video
        | filters.audio
        | filters.animation
    )
    & filters.private
)
async def receive_file(
    client,
    message
):

    user_id = message.from_user.id

    clear_cancel_event(
        user_id
    )

    PENDING_FILES[user_id] = {
        "message": message,
        "name": None
    }

    original_name = get_original_filename(
        message
    )

    await message.reply_text(
        "📁 **File received!**\n\n"
        f"📄 Current name: `{original_name}`\n\n"
        "✏️ Now send the new file name."
    )


# =========================================================
# STEP 2 — RECEIVE NEW NAME
# =========================================================

@Client.on_message(
    filters.text
    & filters.private
    & ~filters.command(
        [
            "start",
            "setting",
            "cancel",
            "setthumb",
            "delthumb"
        ]
    )
)
async def receive_filename(
    client,
    message
):

    user_id = message.from_user.id

    pending = PENDING_FILES.get(
        user_id
    )

    if not pending:
        return

    new_name = (
        message.text or ""
    ).strip()

    if not new_name:

        await message.reply_text(
            "❌ Filename cannot be empty."
        )

        return

    safe_name = safe_filename(
        new_name,
        default="file"
    )

    if not Path(safe_name).stem:

        await message.reply_text(
            "❌ Invalid filename.\n\n"
            "Please send another name."
        )

        return

    pending["name"] = safe_name

    await message.reply_text(
        "✅ **New name received.**\n\n"
        f"📄 `{safe_name}`\n\n"
        "Choose what you want to do:",
        reply_markup=action_keyboard()
    )


# =========================================================
# STEP 3 — RENAME / COMPRESS
# =========================================================

@Client.on_callback_query(
    filters.regex(
        r"^fileaction_(rename|compress)$"
    )
)
async def file_action(
    client,
    query: CallbackQuery
):

    user_id = query.from_user.id

    pending = PENDING_FILES.get(
        user_id
    )

    if not pending:

        await query.answer(
            "❌ This file request has expired.",
            show_alert=True
        )

        return

    action = query.data.split(
        "_",
        1
    )[1]

    source_message = pending["message"]
    new_name = pending["name"]

    if not new_name:

        await query.answer(
            "❌ Filename is missing.",
            show_alert=True
        )

        return

    PENDING_FILES.pop(
        user_id,
        None
    )

    cancel_event = get_cancel_event(
        user_id
    )

    cancel_event.clear()

    await query.answer()

    try:

        await query.message.edit_text(
            "⬇️ **Downloading...**\n\n"
            "Use /cancel to stop."
        )

    except Exception:
        pass

    input_file = None
    output_file = None

    try:

        original_name = get_original_filename(
            source_message
        )

        # ==========================================
        # DOWNLOAD
        # ==========================================

        input_file = await download_file(
            query.message,
            source_message
        )

        if not input_file:

            raise RuntimeError(
                "Download failed."
            )

        input_path = Path(
            input_file
        )

        if cancel_event.is_set():

            raise asyncio.CancelledError()

        # ==========================================
        # OUTPUT NAME
        # ==========================================

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

        # ==========================================
        # RENAME
        # ==========================================

        if action == "rename":

            title = Path(
                output_name
            ).stem

            # --------------------------------------
            # MEDIA FILE
            # --------------------------------------

            if (
                input_path.suffix.lower()
                in MEDIA_EXTENSIONS
            ):

                command = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",

                    "-i",
                    str(input_path),

                    "-map",
                    "0",

                    # REMOVE OLD METADATA
                    "-map_metadata",
                    "-1",

                    # NEW METADATA
                    "-metadata",
                    f"title={title}",

                    "-metadata",
                    "comment=@SKR",

                    # NO RE-ENCODE
                    "-c",
                    "copy",

                    "-y",
                    str(output_file)
                ]

                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                while True:

                    if cancel_event.is_set():

                        try:

                            if process.returncode is None:
                                process.kill()

                        except Exception:
                            pass

                        await process.wait()

                        raise asyncio.CancelledError()

                    try:

                        await asyncio.wait_for(
                            process.communicate(),
                            timeout=0.2
                        )

                        break

                    except asyncio.TimeoutError:

                        continue

                if process.returncode != 0:

                    raise RuntimeError(
                        "FFmpeg metadata update failed."
                    )

                if not output_file.exists():

                    raise RuntimeError(
                        "Renamed output was not created."
                    )

                input_path.unlink()

            # --------------------------------------
            # NON-MEDIA FILE
            # --------------------------------------

            else:

                input_path.rename(
                    output_file
                )

        # ==========================================
        # COMPRESS
        # ==========================================

        else:

            settings = load_settings()

            codec = settings.get(
                "vcodec",
                "libx264"
            )

            crf = settings.get(
                "crf",
                24
            )

            resolution = settings.get(
                "resolution",
                "720p"
            )

            video_quality = settings.get(
                "video_quality",
                "balanced"
            )

            audio_bitrate = settings.get(
                "audio_bitrate",
                "128k"
            )

            await query.message.edit_text(
                "🗜️ **Compressing...**\n\n"
                f"📐 Resolution: `{resolution}`\n"
                f"🎬 Codec: `{codec}`\n"
                f"🔥 Quality: `{video_quality}`\n"
                f"🎚 CRF: `{crf}`\n"
                f"🎵 Audio: `{audio_bitrate}`\n\n"
                "Use /cancel to stop."
            )

            result = await compress_file(
                input_file=input_path,
                output_file=output_file,
                status_message=query.message,
                cancel_event=cancel_event,
                title=Path(
                    output_name
                ).stem
            )

            if not result:
                raise RuntimeError(
                    "Compression failed."
                )

            if not result.get(
                "success"
            ):
                raise RuntimeError(
                    "Compression failed."
                )

            try:

                if input_path.exists():
                    input_path.unlink()

            except Exception:
                pass

        # ==========================================
        # CANCEL CHECK
        # ==========================================

        if cancel_event.is_set():

            raise asyncio.CancelledError()

        # ==========================================
        # THUMBNAIL
        # ==========================================

        thumbnail = await get_thumbnail(
            client
        )

        # ==========================================
        # UPLOAD
        # ==========================================

        await query.message.edit_text(
            "📤 **Uploading...**"
        )

        success = await upload_file(
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

        try:

            await query.message.edit_text(
                "🛑 **Operation cancelled.**"
            )

        except Exception:
            pass

    except Exception as e:

        print(
            f"{action.title()} error:",
            e
        )

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

        try:

            await query.message.edit_text(
                f"❌ **{action.title()} failed.**\n\n"
                f"`{str(e)[:3000]}`"
            )

        except Exception:
            pass

    finally:

        clear_cancel_event(
            user_id
        )
