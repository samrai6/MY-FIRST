import asyncio
import json
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
        "resolution": "720p",
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
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            command,
            stderr=subprocess.DEVNULL
        )

        return max(float(result.decode().strip()), 0.1)

    except Exception:
        return 0.1


async def get_resolution(file_path):
    command = [
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
            command,
            stderr=subprocess.DEVNULL
        )

        value = result.decode().strip()

        width, height = value.split("x")

        return int(width), int(height)

    except Exception:
        return 0, 0


async def get_target_resolution(file_path, resolution_setting):
    width, height = await get_resolution(file_path)

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
        720
    )

    # Never upscale
    if height <= target_height:
        return width, height

    target_width = int(
        width * target_height / height
    )

    # FFmpeg encoding needs even dimensions
    target_width -= target_width % 2
    target_height -= target_height % 2

    target_width = max(target_width, 2)
    target_height = max(target_height, 2)

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


def build_ffmpeg_command(
    input_file,
    output_file,
    width,
    height,
    settings,
    title=None
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

    audio_bitrate = settings.get(
        "audio_bitrate",
        "128k"
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

    if pix_fmt not in (
        "yuv420p",
        "yuv444p",
        "yuv422p"
    ):
        pix_fmt = "yuv420p"

    allowed_audio = (
        "320k",
        "192k",
        "128k",
        "96k",
        "64k"
    )

    if audio_bitrate not in allowed_audio:
        audio_bitrate = "128k"

    scale = (
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",

        "-i", str(input_file),

        "-map", "0:v:0",
        "-map", "0:a?",

        # Remove old metadata
        "-map_metadata", "-1",

        # New metadata
        "-metadata",
        f"title={title}" if title else "title=@SKR",

        "-metadata",
        "comment=@SKR",

        # Video
        "-vf", scale,

        "-c:v", codec,
        "-preset", "ultrafast",
        "-crf", str(crf),
        "-pix_fmt", pix_fmt,

        # Audio
        "-c:a", "aac",
        "-b:a", audio_bitrate,

        # MP4/MKV compatibility
        "-movflags", "+faststart",

        # Progress
        "-progress", "pipe:1",
        "-nostats",

        "-y",
        str(output_file)
    ]

    return command


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
        "720p"
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

    command = build_ffmpeg_command(
        input_file,
        output_file,
        width,
        height,
        settings,
        title=title
    )

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    async with COMPRESSION_LOCK:

        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()

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

                # Cancel check
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

                    quality_name = get_quality_name(
                        settings
                    )

                    text = (
                        "🗜️ **Compressing...**\n\n"
                        f"[{bar}] {percent:.1f}%\n\n"
                        f"📐 Resolution: "
                        f"`{width}x{height}`\n"
                        f"🎬 Codec: "
                        f"`{settings.get('vcodec', 'libx264')}`\n"
                        f"🔥 Quality: "
                        f"`{quality_name}`\n"
                        f"🎚 CRF: "
                        f"`{settings.get('crf', 24)}`\n"
                        f"🎵 Audio: "
                        f"`{settings.get('audio_bitrate', '128k')}`\n"
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
                time.monotonic() -
                start_time
            )

            if status_message:

                try:
                    await status_message.edit_text(
                        "🗜️ **Compression completed!**\n\n"
                        f"📄 `{output_file.name}`\n"
                        f"📐 `{width}x{height}`\n"
                        f"🎬 `{settings.get('vcodec', 'libx264')}`\n"
                        f"🔥 `{get_quality_name(settings)}`\n"
                        f"🎵 `{settings.get('audio_bitrate', '128k')}`\n"
                        f"📦 `{human_size(output_file.stat().st_size)}`\n"
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
                "crf": settings.get(
                    "crf",
                    24
                ),
                "audio_bitrate": settings.get(
                    "audio_bitrate",
                    "128k"
                ),
                "size": output_file.stat().st_size,
                "elapsed": elapsed
            }

        except asyncio.CancelledError:

            if process:

                try:
                    if process.returncode is None:
                        process.kill()
                except Exception:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

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

            if process:

                try:
                    if process.returncode is None:
                        process.kill()
                except Exception:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

            try:
                if output_file.exists():
                    output_file.unlink()
            except Exception:
                pass

            raise


def cleanup_file(file_path):

    if not file_path:
        return

    try:

        path = Path(file_path)

        if path.exists():
            path.unlink()

    except Exception:
        pass
