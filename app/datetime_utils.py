"""Deadline handling assumes the process TZ is Asia/Tashkent (set in app.config),
so Python's naive local datetimes line up with SQLite's datetime('now','localtime')."""

from datetime import datetime
from typing import Optional


def normalize_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_stored_datetime(stored: Optional[str]) -> Optional[datetime]:
    if not stored:
        return None
    return datetime.fromisoformat(stored.replace(" ", "T"))


def format_datetime_uz(stored: Optional[str]) -> str:
    if not stored:
        return ""
    date_part, _, time_part = stored.partition(" ")
    y, m, d = date_part.split("-")
    hm = time_part[:5] if time_part else ""
    return f"{d}.{m}.{y}" + (f" {hm}" if hm else "")
