import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("TZ", "Asia/Tashkent")
try:
    import time

    time.tzset()
except AttributeError:
    pass  # not available on Windows; fine for our Linux deployment target

BASE_DIR = Path(__file__).resolve().parent.parent

PORT = int(os.environ.get("PORT", "3000"))
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-please-use-a-long-random-value")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()


def _clean_bot_username(raw: str) -> str:
    value = raw.strip()
    if value.lower().startswith("https://t.me/"):
        value = value[len("https://t.me/") :]
    if value.startswith("@"):
        value = value[1:]
    return value


BOT_USERNAME = _clean_bot_username(os.environ.get("BOT_USERNAME", ""))

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")

DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "app.db"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))
PUBLIC_DIR = BASE_DIR / "public"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
