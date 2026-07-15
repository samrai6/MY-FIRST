from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters

from pathlib import Path
import shutil
import subprocess
import os
import time
import asyncio
import json

from config import DOWNLOAD_DIR


user_files = {}

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


async def download_file(client, message):
    return await message.download(
        file_name=DOWNLOAD_DIR
    )


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
        "✏️ Send new file name."
    )


@Client.on_message(filters.text & ~filters.command("start"))
async def get_new_name(client, message):

    uid = message.from_user.id

    if uid not in user_files:
        return

    new_name = message.text.strip()

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


@Client.on_callback_query()
async def action_handler(client, query: CallbackQuery):

    uid = query.from_user.id

    if uid not in user_files:
        return


    if query.data == "rename_only":

        await query.message.reply_document(
            document=user_files[uid]["file_path"],
            caption="✅ Rename completed"
        )


    elif query.data == "compress":

        await query.message.reply_text(
            "Select quality:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("360p", callback_data="compress_360"),
                        InlineKeyboardButton("480p", callback_data="compress_480")
                    ],
                    [
                        InlineKeyboardButton("720p", callback_data="compress_720"),
                        InlineKeyboardButton("1080p", callback_data="compress_1080")
                    ]
                ]
            )
        )


    elif query.data.startswith("compress_"):

        quality = query.data.split("_")[1]

        input_path = Path(
            user_files[uid]["file_path"]
        )

        output_file = input_path.with_name(
            f"{input_path.stem}_{quality}p{input_path.suffix}"
        )


        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(input_path),
            "-vf",
            f"scale=-2:{quality}",
            "-c:v",
            "libx264",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-map_metadata",
            "-1",
            "-y",
            str(output_file)
        ]


        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )


        status = await query.message.reply_text(
            "🗜 Compressing..."
        )


        start = time.time()


        await asyncio.to_thread(
            process.wait
        )


        elapsed = int(time.time() - start)


        user_files[uid]["output_file"] = str(output_file)


        await status.edit_text(
            f"✅ Compression Done\n"
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


    elif query.data == "upload_document":

        await query.message.reply_document(
            document=user_files[uid]["output_file"],
            caption="📄 Upload completed ✅"
        )


    elif query.data == "upload_video":

        await query.message.reply_video(
            video=user_files[uid]["output_file"],
            caption="🎬 Upload completed ✅"
        )
