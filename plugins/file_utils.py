import os
import re
from pathlib import Path


# =========================
# SAFE FILENAME
# =========================

def safe_filename(filename, default="file"):

    if not filename:
        return default

    filename = os.path.basename(str(filename))

    filename = re.sub(
        r'[\\/:*?"<>|]',
        "_",
        filename
    )

    filename = re.sub(
        r'\s+',
        " ",
        filename
    ).strip()

    if not filename:
        return default

    return filename


# =========================
# FILE EXTENSION
# =========================

def get_extension(filename):

    if not filename:
        return ""

    return Path(filename).suffix.lower()


# =========================
# FILE NAME WITHOUT EXTENSION
# =========================

def get_filename_without_extension(filename):

    if not filename:
        return ""

    return Path(filename).stem


# =========================
# FILE SIZE
# =========================

def get_file_size(file_path):

    try:

        return os.path.getsize(file_path)

    except Exception:

        return 0


# =========================
# FILE EXISTS
# =========================

def file_exists(file_path):

    try:
        return bool(
            file_path
            and os.path.isfile(file_path)
        )

    except Exception:

        return False


# =========================
# DIRECTORY EXISTS
# =========================

def directory_exists(directory):

    try:
        return bool(
            directory
            and os.path.isdir(directory)
        )

    except Exception:

        return False


# =========================
# ENSURE DIRECTORY
# =========================

def ensure_directory(directory):

    if not directory:
        return False

    try:

        Path(directory).mkdir(
            parents=True,
            exist_ok=True
        )

        return True

    except Exception as e:

        print(
            "Directory create error:",
            e
        )

        return False
