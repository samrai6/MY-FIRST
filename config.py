from os import getenv
from dotenv import load_dotenv

load_dotenv()

API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")
BOT_TOKEN = getenv("BOT_TOKEN")

DOWNLOAD_DIR = "downloads"

# Your Telegram User ID
OWNER_ID = int(getenv("OWNER_ID", "0"))

# Optional: Permanent thumbnail Telegram file_id
THUMB_FILE_ID = getenv("THUMB_FILE_ID")
