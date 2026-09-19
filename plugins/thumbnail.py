import json
import os
from pathlib import Path

from pyrogram import Client, filters

from config import DOWNLOAD_DIR, OWNER_ID, THUMB_FILE_ID


THUMB_SETTINGS_FILE = "thumbnail.json"
THUMB_FILE = str(
    Path(DOWNLOAD_DIR) / "thumbnail.jpg"
)


# =========================
# DIRECTORY
# =========================

Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


# =========================
# LOAD THUMBNAIL FILE ID
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


# =========================
# SAVE THUMBNAIL FILE ID
# =========================

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

        return True

    except Exception as e:
        print(
            "Thumbnail save error:",
            e
        )

        return False


# =========================
# GET THUMBNAIL
# =========================

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

        if (
            result
            and os.path.exists(THUMB_FILE)
        ):
            return THUMB_FILE

    except Exception as e:

        print(
            "Thumbnail download error:",
            e
        )

    return None


# =========================
# /SETTHUMB
# =========================

@Client.on_message(
    filters.command("setthumb")
    & filters.private
)
async def set_thumbnail(client, message):

    if message.from_user.id != OWNER_ID:

        await message.reply_text(
            "❌ Owner only."
        )

        return

    reply = message.reply_to_message

    if not reply:

        await message.reply_text(
            "❌ Reply to an image and use:\n\n"
            "/setthumb"
        )

        return

    media = (
        reply.photo
        or reply.document
    )

    if not media:

        await message.reply_text(
            "❌ Please reply to an image."
        )

        return

    if reply.document:

        mime = reply.document.mime_type or ""

        if not mime.startswith("image/"):

            await message.reply_text(
                "❌ The replied document must be an image."
            )

            return

    try:

        msg = await message.reply_text(
            "⏳ Saving thumbnail..."
        )

        file_id = (
            reply.photo.file_id
            if reply.photo
            else reply.document.file_id
        )

        if not save_thumbnail_file_id(file_id):

            await msg.edit_text(
                "❌ Failed to save thumbnail."
            )

            return

        # Remove old cached thumbnail
        try:
            if os.path.exists(THUMB_FILE):
                os.remove(THUMB_FILE)
        except Exception:
            pass

        await msg.edit_text(
            "✅ Thumbnail saved successfully.\n\n"
            "It will be used for uploads."
        )

    except Exception as e:

        print(
            "Set thumbnail error:",
            e
        )

        await message.reply_text(
            "❌ Failed to set thumbnail."
        )


# =========================
# /DELTHUMB
# =========================

@Client.on_message(
    filters.command("delthumb")
    & filters.private
)
async def delete_thumbnail(client, message):

    if message.from_user.id != OWNER_ID:

        await message.reply_text(
            "❌ Owner only."
        )

        return

    try:

        if os.path.exists(THUMB_SETTINGS_FILE):
            os.remove(THUMB_SETTINGS_FILE)

        if os.path.exists(THUMB_FILE):
            os.remove(THUMB_FILE)

        await message.reply_text(
            "🗑️ Thumbnail removed successfully."
        )

    except Exception as e:

        print(
            "Delete thumbnail error:",
            e
        )

        await message.reply_text(
            "❌ Failed to remove thumbnail."
        )
