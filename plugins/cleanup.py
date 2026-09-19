import os
import shutil
from pathlib import Path

from config import DOWNLOAD_DIR


# =========================
# DIRECTORY
# =========================

Path(DOWNLOAD_DIR).mkdir(
    parents=True,
    exist_ok=True
)


# =========================
# REMOVE FILE
# =========================

def remove_file(file_path):

    if not file_path:
        return False

    try:

        if os.path.isfile(file_path):
            os.remove(file_path)
            return True

    except Exception as e:

        print(
            "File cleanup error:",
            e
        )

    return False


# =========================
# REMOVE DIRECTORY
# =========================

def remove_directory(directory):

    if not directory:
        return False

    try:

        if os.path.isdir(directory):
            shutil.rmtree(directory)
            return True

    except Exception as e:

        print(
            "Directory cleanup error:",
            e
        )

    return False


# =========================
# CLEAN JOB FILES
# =========================

def cleanup_files(*file_paths):

    removed = 0

    for file_path in file_paths:

        if remove_file(file_path):
            removed += 1

    return removed


# =========================
# CLEAN DOWNLOAD DIRECTORY
# =========================

def clean_download_directory():

    removed = 0

    try:

        for item in Path(DOWNLOAD_DIR).iterdir():

            try:

                if item.is_file():

                    item.unlink()
                    removed += 1

                elif item.is_dir():

                    shutil.rmtree(item)
                    removed += 1

            except Exception as e:

                print(
                    "Cleanup item error:",
                    e
                )

    except Exception as e:

        print(
            "Download directory cleanup error:",
            e
        )

    return removed
