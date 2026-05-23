import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "chat.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylda kiritilmagan.")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_IDS .env faylda kiritilmagan. Masalan: ADMIN_IDS=123,456")
