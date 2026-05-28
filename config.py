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

# ── Office hours ──────────────────────────────────────────────────────────────
OFFICE_OPEN:  int = int(os.getenv("OFFICE_OPEN",  "10"))
OFFICE_CLOSE: int = int(os.getenv("OFFICE_CLOSE", "22"))

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

# ── Multi-club configuration ──────────────────────────────────────────────────
# Passwords are loaded from environment variables (set in .env / Render dashboard).
# Center Club keeps its fixed password; all others read from env.
CLUBS: dict[str, dict] = {
    "abovyan":    {"name": "Abovyan",      "password": os.getenv("CLUB_PASSWORD_ABOVYAN",    "Abovyan3.16")},
    "joyful":     {"name": "Joyful",       "password": os.getenv("CLUB_PASSWORD_JOYFUL",     "Joyful3.16")},
    "ararat":     {"name": "Ararat",       "password": os.getenv("CLUB_PASSWORD_ARARAT",     "Ararat3.16")},
    "eghvard":    {"name": "Eghvard",      "password": os.getenv("CLUB_PASSWORD_EGHVARD",    "Eghvard3.16")},
    "club36":     {"name": "Club 36",      "password": os.getenv("CLUB_PASSWORD_CLUB36",     "Club 363.16")},
    "davtashen":  {"name": "Davtashen",    "password": os.getenv("CLUB_PASSWORD_DAVTASHEN",  "Davtashen3.16")},
    "mix":        {"name": "Mix",          "password": os.getenv("CLUB_PASSWORD_MIX",        "Mix3.16")},
    "kievyan":    {"name": "Kievyan",      "password": os.getenv("CLUB_PASSWORD_KIEVYAN",    "Kievyan3.16")},
    "monument":   {"name": "Monument",     "password": os.getenv("CLUB_PASSWORD_MONUMENT",   "Monument3.16")},
    "shengavit":  {"name": "Shengavit",    "password": os.getenv("CLUB_PASSWORD_SHENGAVIT",  "Shengavit3.16")},
    "hrazdan":    {"name": "Hrazdan",      "password": os.getenv("CLUB_PASSWORD_HRAZDAN",    "Hrazdan3.16")},
    "avan":       {"name": "Avan",         "password": os.getenv("CLUB_PASSWORD_AVAN",       "Avan3.16")},
    "unity":      {"name": "Unity",        "password": os.getenv("CLUB_PASSWORD_UNITY",      "Unity3.16")},
    "kvartall":   {"name": "Kvartall",     "password": os.getenv("CLUB_PASSWORD_KVARTALL",   "Kvartall3.16")},
    "revive":     {"name": "Revive",       "password": os.getenv("CLUB_PASSWORD_REVIVE",     "Revive3.16")},
    "centerclub": {"name": "Center Club",  "password": "Center Club3.16"},
    "stage":      {"name": "Stage",        "password": os.getenv("CLUB_PASSWORD_STAGE",      "Stage3.16")},
}


def verify_club_password(club_id: str, entered: str) -> bool:
    """Return True if entered matches the club's password."""
    club = CLUBS.get(club_id)
    if not club:
        return False
    return entered == club["password"]


def get_club_name(club_id: str) -> str:
    """Return the display name for a club_id, or the raw id if unknown."""
    club = CLUBS.get(club_id)
    return club["name"] if club else club_id


# ── ConversationHandler states ────────────────────────────────────────────────
(
    STATE_PICK_DATE,          # 0
    STATE_PICK_HOUR,          # 1
    STATE_PICK_START_MINUTE,  # 2
    STATE_PICK_END_HOUR,      # 3
    STATE_PICK_END_MINUTE,    # 4
    STATE_ENTER_TITLE,        # 5
    STATE_CONFIRM,            # 6
    STATE_EDIT_PICK_FIELD,    # 7
    STATE_EDIT_ENTER_VALUE,   # 8
    STATE_PICK_CLUB,          # 9
    STATE_ENTER_PASSWORD,     # 10
) = range(11)

# Aliases used by the hybrid slot picker in handlers/booking.py
STATE_PICK_START = STATE_PICK_HOUR
STATE_PICK_END   = STATE_PICK_END_HOUR
