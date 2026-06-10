from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    SAMARKAND_TZ = ZoneInfo("Asia/Samarkand")
except ZoneInfoNotFoundError:
    # Agar VPSda tzdata bo'lmasa ham Uzbekistan vaqti UTC+5 bo'lib ishlaydi.
    SAMARKAND_TZ = timezone(timedelta(hours=5), name="Asia/Samarkand")


def now_samarkand() -> datetime:
    return datetime.now(SAMARKAND_TZ)


def now_samarkand_str() -> str:
    return now_samarkand().strftime("%Y-%m-%d %H:%M:%S")


def format_samarkand(value, default: str = "—") -> str:
    """SQLite UTC/CURRENT_TIMESTAMP qiymatini Asia/Samarkand ko'rinishida chiqaradi."""
    if value is None or value == "":
        return default
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return default
        try:
            # SQLite CURRENT_TIMESTAMP odatda: 2026-06-10 12:49:48 (UTC)
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    # DBdagi timezone yo'q vaqtlarni UTC deb qabul qilamiz va Samarqandga o'tkazamiz.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAMARKAND_TZ).strftime("%Y-%m-%d %H:%M:%S")
