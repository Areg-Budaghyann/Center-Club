"""
config.py
---------
Centralised configuration. All env vars and constants live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ─────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

_raw_group = os.getenv("GROUP_CHAT_ID", "")
GROUP_CHAT_ID: int | None = int(_raw_group) if _raw_group.lstrip("-").isdigit() else None

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "office.db")

# ── Office hours — 24 hours, no restrictions ─────────────────────────────────
OFFICE_OPEN:  int = 0    # 00:00
OFFICE_CLOSE: int = 24   # covers full day

# ── Booking limits ────────────────────────────────────────────────────────────
MAX_DURATION_HOURS: int = 12
MIN_DURATION_HOURS: int = 1

# ── Reminder ──────────────────────────────────────────────────────────────────
REMINDER_MINUTES_BEFORE: int = 60

# ── Admin users ───────────────────────────────────────────────────────────────
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

# ── ConversationHandler states ────────────────────────────────────────────────
(
    STATE_PICK_DATE,
    STATE_PICK_HOUR,
    STATE_PICK_DURATION,
    STATE_ENTER_TITLE,
    STATE_CONFIRM,
    STATE_EDIT_PICK_FIELD,
    STATE_EDIT_ENTER_VALUE,
) = range(7)
