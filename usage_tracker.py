"""Local monthly Azure Translator character usage tracking."""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import date
from pathlib import Path


MONTHLY_LIMIT = 2_000_000
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
USAGE_FILE = APP_DIR / "usage.json"
_LOCK = threading.Lock()


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def next_reset_date() -> date:
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def count_azure_characters(text: str) -> int:
    """Count UTF-16 code units, matching Azure's surrogate-pair counting."""
    return len(text.encode("utf-16-le")) // 2


def _read_unlocked() -> int:
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return 0
    if data.get("month") != current_month():
        return 0
    try:
        return max(0, int(data.get("used", 0)))
    except (TypeError, ValueError):
        return 0


def get_usage() -> int:
    with _LOCK:
        return _read_unlocked()


def add_usage(texts: list[str]) -> int:
    characters = sum(count_azure_characters(text) for text in texts)
    with _LOCK:
        used = _read_unlocked() + characters
        payload = {"month": current_month(), "used": used}
        temporary = USAGE_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, USAGE_FILE)
        return used

