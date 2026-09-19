from pathlib import Path

from pyrogram import Client, filters

from config import DOWNLOAD_DIR
from .file_utils import safe_filename, get_extension
from .progress import make_download_callback, make_upload_callback
from .thumbnail import get_thumbnail


def build_renamed_filename(original_name, new_name):
    original_ext = get_extension(original_name)

    new_name = safe_filename(new_name, default="file")
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


async def download_file(status, source_message):
    callback = make_download_callback(
        status,
        action="⬇️ Downloading..."
    )

    return await source_message.download(
        file_name=DOWNLOAD_DIR,
        progress=callback
    )


async def upload_file(status, file_path, thumbnail=None):
    file_path = Path(file_path)

    if not file_path.exists():
        return False

    callback = make_upload_callback(
        status,
        action="📤 Uploading..."
    )

    try:
        if file_path.suffix.lower() in (
            ".mp4",
            ".mkv",
            ".webm",
            ".mov",
            ".avi"
        ):
            kwargs = {
                "video": str(file_path),
                "progress": callback
            }

            if thumbnail and Path(thumbnail).exists():
                kwargs["thumb"] = thumbnail

            await status.reply_video(**kwargs)
            return True

    except Exception as e:
        print("Video upload failed:", e)

    try:
        await status.reply_document(
            document=str(file_path),
            progress=callback
        )
        return True

    except Exception as e:
        print("Document upload failed:", e)
        return False


@Client.on_message(
    filters.command("rename")
    & filters.private
)
async def rename_command(client, message):
    reply = message.reply_to_message

    if not reply:
        await message.reply_text(
            "❌ Reply to a file/video and use:\n\n"
            "/rename New Name"
        )
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        await message.reply_text(
            "❌ Give a new filename.\n\n"
            "Example:\n"
            "/rename My Video"
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
        original_name = get_original_filename(reply)

        input_file = await download_file(
            status,
            reply
        )

        if not input_file:
            raise RuntimeError("Download failed.")

        input_path = Path(input_file)

        output_name = build_renamed_filename(
            original_name,
            new_name
        )

        output_file = input_path.parent / output_name

        if output_file.exists():
            output_file.unlink()

        input_path.rename(output_file)

        thumbnail = await get_thumbnail(client)

        await status.edit_text(
            "📤 Uploading..."
        )

        success = await upload_file(
            status,
            output_file,
            thumbnail
        )

        if not success:
            raise RuntimeError("Upload failed.")

        try:
            await status.delete()
        except Exception:
            pass

    except Exception as e:
        print("Rename error:", e)

        try:
            await status.edit_text(
                "❌ Rename failed.\n\n"
                + str(e)[:3000]
            )
        except Exception:
            pass

    finally:
        for path in (input_file, output_file):
            try:
                if path:
                    file_path = Path(path)

                    if file_path.exists():
                        file_path.unlink()

            except Exception:
                pass
