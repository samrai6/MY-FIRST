from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters

from pathlib import Path
import shutil
import subprocess
import os

from config import DOWNLOAD_DIR


user_files = {}

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


async def download_file(client, message):
    file_path = await message.download(
        file_name=DOWNLOAD_DIR
    )
    return file_path


@Client.on_message(
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.animation
)
async def file_handler(client, message):

    user_files[message.from_user.id] = {
        "message": message,
        "file_path": None
    }

    await message.reply_text(
        "📁 File received!\n\n"
        "✏️ Now send me the new file name.\n\n"
        "Example:\nMovie 2026"
    )


@Client.on_message(filters.text & ~filters.command("start"))
async def get_new_name(client, message):

    uid = message.from_user.id

    if uid not in user_files:
        return

    new_name = message.text.strip()

    await message.reply_text(
        "⬇️ Downloading file...\n\n"
        "⏳ Please wait..."
    )


    file_path = await download_file(
        client,
        user_files[uid]["message"]
    )


    await message.reply_text(
        "📝 Renaming file..."
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


@Client.on_callback_query()
async def action_handler(client, query: CallbackQuery):

    uid = query.from_user.id


    if uid not in user_files:
        return


    if query.data == "rename_only":

        await query.answer(
            "Rename selected ✅"
        )

        await query.message.reply_document(
            document=user_files[uid]["file_path"],
            caption="📄 Rename completed ✅"
        )


    elif query.data == "compress":

        await query.answer(
            "Compress selected ✅"
        )

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


    elif query.data.startswith("compress_"):

        quality = query.data.split("_")[1]


        await query.answer(
            "Compressing..."
        )


        await query.message.reply_text(
            f"🗜 Compressing {quality}p...\n⏳ Please wait..."
        )


        input_file = user_files[uid]["file_path"]

        input_path = Path(input_file)

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p{input_path.suffix}"
        )


        cmd = [
    "ffmpeg",
    "-hide_banner",
    "-nostats",
    "-progress", "pipe:1",
    "-threads", "0",
    "-i", str(input_path),
    "-vf", f"scale=-2:{quality}",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "24",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-c:a", "aac",
    "-b:a", "96k",
    "-ac", "2",
    "-y",
    str(output_file)
]


        process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    universal_newlines=True
)

status = await query.message.reply_text(
    "🗜 Compressing...\n0%"
)
import time

start = time.time()

for line in process.stdout:
    line = line.strip()

    if line.startswith("out_time_ms="):
        try:
            current = int(line.split("=")[1]) / 1000000
            elapsed = int(time.time() - start)

            await status.edit_text(
                f"🗜 Compressing {quality}p...\n\n"
                f"⏱ Elapsed: {elapsed}s"
            )
        except:
            pass

process.wait()

await status.edit_text("📤 Uploading...")
