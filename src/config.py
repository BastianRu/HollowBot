import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "src" / "data"
DATABASE_PATH = PROJECT_ROOT / "bot_metrics.db"

TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "@TheHollowPianist")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "URL_NOT_SET")
BOT_TOKEN = os.getenv("BOT_TOKEN", "_")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "NO_KEY_FOUND")
CURRENT_VER = os.getenv("CURRENT_VER", "0.0.3")
