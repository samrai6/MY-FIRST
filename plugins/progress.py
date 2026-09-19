import time
import asyncio


# =========================
# PROGRESS HELPERS
# =========================

def human_size(size):
    size = float(size or 0)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size:.1f} PB"


def human_speed(speed):
    return f"{human_size(speed)}/s"


def human_time(seconds):
    if seconds is None or seconds < 0:
        return "--:--"

    seconds = int(seconds)

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def progress_bar(percent, length=12):
    percent = max(0, min(100, float(percent)))

    filled = int(length * percent / 100)

    return (
        "█" * filled +
        "░" * (length - filled)
    )


def calculate_progress(current, total, start_time):
    now = time.monotonic()

    elapsed = max(now - start_time, 0.001)

    percent = 0

    if total:
        percent = min(
            100,
            (current / total) * 100
        )

    speed = current / elapsed

    remaining = 0

    if speed > 0 and total:
        remaining = max(
            (total - current) / speed,
            0
        )

    return {
        "percent": percent,
        "speed": speed,
        "eta": remaining,
        "elapsed": elapsed,
    }


# =========================
# TELEGRAM PROGRESS
# =========================

class ProgressTracker:

    def __init__(
        self,
        message,
        action="Processing",
        update_interval=2.0
    ):
        self.message = message
        self.action = action
        self.update_interval = update_interval

        self.start_time = time.monotonic()
        self.last_update = 0

        self.last_current = 0
        self.last_time = self.start_time

        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def is_cancelled(self):
        return self.cancelled

    async def update(
        self,
        current,
        total,
        extra=""
    ):
        if self.cancelled:
            return

        now = time.monotonic()

        # Avoid Telegram flood
        if (
            now - self.last_update < self.update_interval
            and current < total
        ):
            return

        self.last_update = now

        elapsed = max(
            now - self.start_time,
            0.001
        )

        percent = 0

        if total:
            percent = min(
                100,
                current * 100 / total
            )

        speed = current / elapsed

        eta = 0

        if speed > 0 and total:
            eta = max(
                (total - current) / speed,
                0
            )

        bar = progress_bar(percent)

        text = (
            f"{self.action}\n\n"
            f"[{bar}] {percent:.1f}%\n\n"
            f"📦 {human_size(current)} / "
            f"{human_size(total)}\n"
            f"⚡ Speed: {human_speed(speed)}\n"
            f"⏳ ETA: {human_time(eta)}\n"
            f"🕐 Elapsed: {human_time(elapsed)}"
        )

        if extra:
            text += f"\n\n{extra}"

        try:
            await self.message.edit_text(text)
        except Exception:
            pass


# =========================
# DOWNLOAD CALLBACK
# =========================

def make_download_callback(
    message,
    action="⬇️ Downloading",
    update_interval=2.0
):
    tracker = ProgressTracker(
        message,
        action=action,
        update_interval=update_interval
    )

    async def callback(current, total):
        await tracker.update(
            current,
            total
        )

    callback.tracker = tracker

    return callback


# =========================
# UPLOAD CALLBACK
# =========================

def make_upload_callback(
    message,
    action="📤 Uploading",
    update_interval=2.0
):
    tracker = ProgressTracker(
        message,
        action=action,
        update_interval=update_interval
    )

    async def callback(current, total):
        await tracker.update(
            current,
            total
        )

    callback.tracker = tracker

    return callback


# =========================
# GENERIC PROGRESS CALLBACK
# =========================

def make_progress_callback(
    message,
    action="⚙️ Processing",
    update_interval=2.0
):
    tracker = ProgressTracker(
        message,
        action=action,
        update_interval=update_interval
    )

    async def callback(current, total):
        await tracker.update(
            current,
            total
        )

    callback.tracker = tracker

    return callback


# =========================
# SAFE FINAL UPDATE
# =========================

async def final_progress(
    message,
    title,
    elapsed=None,
    extra=""
):
    text = title

    if elapsed is not None:
        text += (
            f"\n\n🕐 Elapsed: "
            f"{human_time(elapsed)}"
        )

    if extra:
        text += f"\n\n{extra}"

    try:
        await message.edit_text(text)
    except Exception:
        pass
