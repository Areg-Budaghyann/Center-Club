"""
config.py
---------
Centralised configuration. All env vars and constants live here.
Import this module everywhere instead of reading os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Optional: group chat that receives new-booking notifications.
# Set to None to disable group notifications.
_raw_group = os.getenv("GROUP_CHAT_ID", "")
GROUP_CHAT_ID: int | None = int(_raw_group) if _raw_group.lstrip("-").isdigit() else None

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "office.db")

# ── Office hours ─────────────────────────────────────────────────────────────
OFFICE_OPEN: int  = int(os.getenv("OFFICE_OPEN",  "10"))   # inclusive hour
OFFICE_CLOSE: int = int(os.getenv("OFFICE_CLOSE", "23"))   # exclusive hour

# ── Booking limits ────────────────────────────────────────────────────────────
MAX_DURATION_HOURS: int = 6
MIN_DURATION_HOURS: int = 1

# ── Reminder ──────────────────────────────────────────────────────────────────
REMINDER_MINUTES_BEFORE: int = 60  # send reminder 60 min before start

# ── Admin users ───────────────────────────────────────────────────────────────
# Comma-separated Telegram user IDs that can create recurring bookings.
# Example in .env:  ADMIN_IDS=123456789,987654321
# Leave empty to allow ALL users to use the recurring booking feature.
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