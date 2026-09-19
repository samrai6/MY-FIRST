import asyncio
import json
import subprocess
import time
from pathlib import Path

from .progress import human_size, human_speed, human_time, progress_bar


SETTINGS_FILE = "compress_settings.json"

# Only ONE FFmpeg job at a time
COMPRESSION_LOCK = asyncio.Lock()


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
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            data = {}

        for key, value in default.items():
            data.setdefault(key, value)

        return data

    except Exception:
        return default


# =========================
# VIDEO INFORMATION
# =========================

async def get_duration(file_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            cmd,
            stderr=subprocess.DEVNULL
        )

        return max(
            float(result.decode().strip()),
            0.1
        )

    except Exception:
        return 0.1


async def get_resolution(file_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(file_path)
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            cmd,
            stderr=subprocess.DEVNULL
        )

        value = result.decode().strip()

        width, height = value.split("x")

        return int(width), int(height)

    except Exception:
        return 0, 0


# =========================
# TARGET RESOLUTION
# =========================

async def get_target_resolution(file_path, quality):
    width, height = await get_resolution(file_path)

    if not width or not height:
        return None

    target_height = int(quality)

    # Never upscale
    if height <= target_height:
        return width, height

    target_width = int(
        width * target_height / height
    )

    # FFmpeg requires even dimensions
    target_width -= target_width % 2
    target_height -= target_height % 2

    if target_width < 2:
        target_width = 2

    if target_height < 2:
        target_height = 2

    return target_width, target_height


# =========================
# FFMPEG COMMAND
# =========================

def build_ffmpeg_command(
    input_file,
    output_file,
    width,
    height,
    settings
):
    codec = settings.get(
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

    try:
        crf = int(crf)
    except Exception:
        crf = 24

    if codec not in (
        "libx264",
        "libx265"
    ):
        codec = "libx264"

    # 10-bit pixel format can fail with some
    # combinations. Keep configured value but
    # fallback is handled by FFmpeg failure.
    if not isinstance(pix_fmt, str):
        pix_fmt = "yuv420p"

    scale = (
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )

    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",

        "-i", str(input_file),

        "-map", "0:v:0",
        "-map", "0:a?",

        "-vf", scale,

        "-c:v", codec,
        "-preset", "medium",
        "-crf", str(crf),
        "-pix_fmt", pix_fmt,

        "-c:a", "aac",
        "-b:a", "128k",

        "-movflags", "+faststart",

        "-progress", "pipe:1",
        "-nostats",

        "-y",
        str(output_file)
    ]


# =========================
# FFMPEG PROGRESS
# =========================

async def compress_file(
    input_file,
    output_file,
    quality,
    status_message,
    cancel_event=None
):
    input_file = Path(input_file)
    output_file = Path(output_file)

    if not input_file.exists():
        raise FileNotFoundError(
            "Input file not found."
        )

    resolution = await get_target_resolution(
        input_file,
        quality
    )

    if not resolution:
        raise RuntimeError(
            "Unable to detect video resolution."
        )

    width, height = resolution

    settings = load_settings()

    duration = await get_duration(
        input_file
    )

    command = build_ffmpeg_command(
        input_file,
        output_file,
        width,
        height,
        settings
    )

    async with COMPRESSION_LOCK:

        start_time = time.monotonic()
        last_update = 0
        process = None

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            while True:

                if cancel_event and cancel_event.is_set():

                    try:
                        process.kill()
                    except Exception:
                        pass

                    await process.wait()

                    raise asyncio.CancelledError()

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

                if key != "out_time_ms":
                    continue

                try:
                    current = int(value) / 1_000_000
                except Exception:
                    continue

                percent = min(
                    100,
                    max(
                        0,
                        current / duration * 100
                    )
                )

                now
