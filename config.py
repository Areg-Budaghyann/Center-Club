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
# Maps club_id → {name, env}  where env is the .env variable holding the password.
CLUBS: dict[str, dict] = {
    "abovyan":     {"name": "Abovyan",     "env": "CLUB_PASSWORD_ABOVYAN"},
    "arabkir":     {"name": "Arabkir",     "env": "CLUB_PASSWORD_ARABKIR"},
    "avan":        {"name": "Avan",        "env": "CLUB_PASSWORD_AVAN"},
    "davtashen":   {"name": "Davtashen",   "env": "CLUB_PASSWORD_DAVTASHEN"},
    "erebuni":     {"name": "Erebuni",     "env": "CLUB_PASSWORD_EREBUNI"},
    "kanaker":     {"name": "Kanaker",     "env": "CLUB_PASSWORD_KANAKER"},
    "kentron":     {"name": "Kentron",     "env": "CLUB_PASSWORD_KENTRON"},
    "malatia":     {"name": "Malatia",     "env": "CLUB_PASSWORD_MALATIA"},
    "nork":        {"name": "Nork",        "env": "CLUB_PASSWORD_NORK"},
    "norknork":    {"name": "Nork-Marash", "env": "CLUB_PASSWORD_NORKNORK"},
    "nubarashen":  {"name": "Nubarashen",  "env": "CLUB_PASSWORD_NUBARASHEN"},
    "shengavit":   {"name": "Shengavit",   "env": "CLUB_PASSWORD_SHENGAVIT"},
    "vardashen":   {"name": "Vardashen",   "env": "CLUB_PASSWORD_VARDASHEN"},
    "yerevan":     {"name": "Yerevan",     "env": "CLUB_PASSWORD_YEREVAN"},
    "ajapnyak":    {"name": "Ajapnyak",    "env": "CLUB_PASSWORD_AJAPNYAK"},
    "zoravar":     {"name": "Zoravar",     "env": "CLUB_PASSWORD_ZORAVAR"},
    "mashtots":    {"name": "Mashtots",    "env": "CLUB_PASSWORD_MASHTOTS"},
}


def verify_club_password(club_id: str, entered: str) -> bool:
    """Return True if entered matches the club's configured password."""
    club = CLUBS.get(club_id)
    if not club:
        return False
    expected = os.getenv(club["env"], "")
    return bool(expected) and entered == expected


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
