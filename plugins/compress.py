import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

from .progress import human_size, human_time, progress_bar


SETTINGS_FILE = "settings.json"

COMPRESSION_LOCK = asyncio.Lock()


def load_settings():
    default = {
        "vcodec": "libx264",
        "crf": 24,
        "pix_fmt": "yuv420p",
        "upload_mode": "video",
        "resolution": "original",
        "video_quality": "balanced",
        "audio_bitrate": "128k"
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


async def get_duration(file_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            command,
            stderr=subprocess.DEVNULL
        )

        return max(
            float(result.decode().strip()),
            0.1
        )

    except Exception:
        return 0.1


async def get_resolution(file_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        str(file_path)
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            command,
            stderr=subprocess.DEVNULL
        )

        value = result.decode().strip()

        width, height = value.split("x")

        return int(width), int(height)

    except Exception:
        return 0, 0


async def get_target_resolution(
    file_path,
    resolution_setting
):
    width, height = await get_resolution(
        file_path
    )

    if not width or not height:
        return None

    if resolution_setting == "original":
        return width, height

    targets = {
        "1080p": 1080,
        "720p": 720,
        "480p": 480
    }

    target_height = targets.get(
        resolution_setting,
        height
    )

    # Never upscale
    if height <= target_height:
        return width, height

    target_width = int(
        width * target_height / height
    )

    # FFmpeg-friendly even dimensions
    target_width -= target_width % 2
    target_height -= target_height % 2

    target_width = max(
        target_width,
        2
    )

    target_height = max(
        target_height,
        2
    )

    return target_width, target_height


def get_quality_name(settings):
    quality = settings.get(
        "video_quality",
        "balanced"
    )

    names = {
        "high": "High",
        "balanced": "Balanced",
        "small": "Small",
        "verysmall": "Very Small"
    }

    return names.get(
        quality,
        "Balanced"
    )


def get_audio_bitrate(settings):
    allowed = {
        "320k": 320,
        "192k": 192,
        "128k": 128,
        "96k": 96,
        "64k": 64
    }

    value = settings.get(
        "audio_bitrate",
        "128k"
    )

    if value not in allowed:
        value = "128k"

    return value, allowed[value]


def calculate_target_bitrate(
    input_size,
    duration,
    audio_kbps=128,
    target_ratio=0.60
):
    """
    Calculate video bitrate for target output size.

    target_ratio:
        0.60 = output approximately 60%
        of original size.

    Example:
        2 GB -> approximately 1.2 GB
    """

    if duration <= 0:
        duration = 1

    target_size = int(
        input_size * target_ratio
    )

    # Convert target bytes to kilobits
    target_kbits = (
        target_size * 8 / 1000
    )

    # Total audio bitrate
    audio_total_kbits = (
        audio_kbps * duration
    )

    # Container overhead reserve
    overhead = 0.94

    video_kbits = (
        target_kbits * overhead
    ) - audio_total_kbits

    # Safe minimum bitrate
    video_bitrate_kbps = max(
        int(video_kbits / duration),
        250
    )

    return video_bitrate_kbps


def build_pass1_command(
    input_file,
    null_output,
    width,
    height,
    video_bitrate,
    pix_fmt
):
    scale = (
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )

    command = [
        "ffmpeg",

        "-hide_banner",
        "-loglevel",
        "error",

        "-i",
        str(input_file),

        "-map",
        "0:v:0",

        "-vf",
        scale,

        "-c:v",
        "libx264",

        "-preset",
        "slow",

        "-b:v",
        f"{video_bitrate}k",

        "-pix_fmt",
        pix_fmt,

        "-pass",
        "1",

        "-passlogfile",
        "skr_compress",

        "-an",

        # Live progress output
        "-progress",
        "pipe:1",

        "-nostats",

        "-f",
        "null",

        null_output
    ]

    return command


def build_pass2_command(
    input_file,
    output_file,
    width,
    height,
    video_bitrate,
    audio_bitrate,
    pix_fmt
):
    scale = (
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )

    command = [
        "ffmpeg",

        "-hide_banner",
        "-loglevel",
        "error",

        "-i",
        str(input_file),

        "-map",
        "0:v:0",

        "-map",
        "0:a?",

        # Remove old global metadata
        "-map_metadata",
        "-1",

        # Remove chapters
        "-map_chapters",
        "-1",

        # General metadata
        "-metadata",
        "title=@SKR",

        "-metadata",
        "comment=@SKR",

        # Video metadata
        "-metadata:s:v:0",
        "title=@SKR",

        # Audio metadata
        "-metadata:s:a:0",
        "title=@SKR",

        # Video
        "-vf",
        scale,

        "-c:v",
        "libx264",

        "-preset",
        "slow",

        "-b:v",
        f"{video_bitrate}k",

        "-pix_fmt",
        pix_fmt,

        "-pass",
        "2",

        "-passlogfile",
        "skr_compress",

        # Audio
        "-c:a",
        "aac",

        "-b:a",
        audio_bitrate,

        "-movflags",
        "+faststart",

        # Live progress output
        "-progress",
        "pipe:1",

        "-nostats",

        "-y",

        str(output_file)
    ]

    return command


async def run_process(
    command,
    duration,
    status_message=None,
    cancel_event=None,
    width=0,
    height=0,
    settings=None,
    phase="Compressing"
):
    start_time = time.monotonic()

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    last_update = 0

    while True:

        # Check cancellation
        if cancel_event and cancel_event.is_set():

            try:
                if process.returncode is None:
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

        now = time.monotonic()

        # Update every ~2 seconds
        if (
            now - last_update < 2
            and percent < 100
        ):
            continue

        last_update = now

        elapsed = max(
            now - start_time,
            0.001
        )

        speed = current / elapsed

        eta = 0

        if speed > 0:
            eta = max(
                duration - current,
                0
            ) / speed

        if status_message:

            bar = progress_bar(
                percent
            )

            text = (
                "🗜️ **Compressing...**\n\n"
                f"[{bar}] {percent:.1f}%\n\n"
                f"📐 Resolution: "
                f"`{width}x{height}`\n"
                f"🎬 Codec: `H264`\n"
                f"⚡ Speed: "
                f"`{speed:.2f}x`\n"
                f"⏳ ETA: "
                f"`{human_time(eta)}`\n"
                f"🕐 Elapsed: "
                f"`{human_time(elapsed)}`"
            )

            try:
                await status_message.edit_text(
                    text
                )
            except Exception:
                pass

    stderr_data = await process.stderr.read()

    return_code = await process.wait()

    if return_code != 0:

        error_text = stderr_data.decode(
            "utf-8",
            errors="ignore"
        ).strip()

        raise RuntimeError(
            error_text or
            "FFmpeg compression failed."
        )


async def compress_file(
    input_file,
    output_file,
    quality=None,
    status_message=None,
    cancel_event=None,
    title=None
):
    input_file = Path(input_file)
    output_file = Path(output_file)

    if not input_file.exists():
        raise FileNotFoundError(
            "Input file not found."
        )

    settings = load_settings()

    resolution_setting = settings.get(
        "resolution",
        "original"
    )

    resolution = await get_target_resolution(
        input_file,
        resolution_setting
    )

    if not resolution:
        raise RuntimeError(
            "Unable to detect video resolution."
        )

    width, height = resolution

    duration = await get_duration(
        input_file
    )

    input_size = input_file.stat().st_size

    audio_bitrate, audio_kbps = get_audio_bitrate(
        settings
    )

    # Default target:
    # approximately 60% of original size
    target_ratio = 0.60

    video_bitrate = calculate_target_bitrate(
        input_size=input_size,
        duration=duration,
        audio_kbps=audio_kbps,
        target_ratio=target_ratio
    )

    pix_fmt = settings.get(
        "pix_fmt",
        "yuv420p"
    )

    if pix_fmt not in (
        "yuv420p",
        "yuv444p",
        "yuv422p"
    ):
        pix_fmt = "yuv420p"

    null_output = (
        "NUL"
        if os.name == "nt"
        else "/dev/null"
    )

    pass1 = build_pass1_command(
        input_file,
        null_output,
        width,
        height,
        video_bitrate,
        pix_fmt
    )

    pass2 = build_pass2_command(
        input_file,
        output_file,
        width,
        height,
        video_bitrate,
        audio_bitrate,
        pix_fmt
    )

    async with COMPRESSION_LOCK:

        start_time = time.monotonic()

        try:

            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()

            # =========================
            # INTERNAL PASS 1
            # =========================

            await run_process(
                pass1,
                duration,
                status_message=status_message,
                cancel_event=cancel_event,
                width=width,
                height=height,
                settings=settings,
                phase="Compressing"
            )

            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()

            # =========================
            # INTERNAL PASS 2
            # =========================

            await run_process(
                pass2,
                duration,
                status_message=status_message,
                cancel_event=cancel_event,
                width=width,
                height=height,
                settings=settings,
                phase="Compressing"
            )

            if not output_file.exists():
                raise RuntimeError(
                    "FFmpeg finished but output "
                    "file was not created."
                )

            if output_file.stat().st_size <= 0:
                raise RuntimeError(
                    "Output file is empty."
                )

            elapsed = (
                time.monotonic()
                - start_time
            )

            output_size = (
                output_file.stat().st_size
            )

            if status_message:

                try:
                    await status_message.edit_text(
                        "🗜️ **Compression completed!**\n\n"
                        f"📄 `{output_file.name}`\n"
                        f"📐 `{width}x{height}`\n"
                        f"🎬 `H264`\n"
                        f"📦 `{human_size(output_size)}`\n"
                        f"🕐 `{human_time(elapsed)}`"
                    )
                except Exception:
                    pass

            return {
                "success": True,
                "output": str(output_file),
                "width": width,
                "height": height,
                "resolution": resolution_setting,
                "quality": settings.get(
                    "video_quality",
                    "balanced"
                ),
                "video_bitrate": video_bitrate,
                "audio_bitrate": audio_bitrate,
                "target_ratio": target_ratio,
                "size": output_size,
                "elapsed": elapsed
            }

        except asyncio.CancelledError:

            try:
                if output_file.exists():
                    output_file.unlink()
            except Exception:
                pass

            if status_message:

                try:
                    await status_message.edit_text(
                        "🛑 **Compression cancelled.**"
                    )
                except Exception:
                    pass

            raise

        except Exception:

            try:
                if output_file.exists():
                    output_file.unlink()
            except Exception:
                pass

            raise

        finally:

            # Remove 2-pass log files
            for file in (
                Path("skr_compress-0.log"),
                Path("skr_compress-0.log.mbtree"),
                Path("ffmpeg2pass-0.log"),
                Path("ffmpeg2pass-0.log.mbtree")
            ):
                try:
                    if file.exists():
                        file.unlink()
                except Exception:
                    pass


def cleanup_file(file_path):

    if not file_path:
        return

    try:

        path = Path(file_path)

        if path.exists():
            path.unlink()

    except Exception:
        pass
