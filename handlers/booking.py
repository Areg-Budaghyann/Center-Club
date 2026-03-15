"""
handlers/booking.py
====================
Multi-step office booking flow via Telegram inline keyboards.

Flow:
    [book] → Month → Day → Hour → Duration → Title → Confirm

Changes in this version:
    - Year step removed: flow starts directly at month selection
    - Month grid shows current + next 11 months (rolling 12-month window)
    - Multi-language support: EN / RU / HY via TEXTS dict + get_text()
    - Language stored in context.user_data["lang"]
    - "No bookings for this day" message shown when day is empty
    - Improved conflict UX: blocked at hour selection level with alert
    - Booking validation extracted into _has_conflict()
"""

import calendar
import logging
from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from translations import get_text, MONTH_NAMES, WEEKDAY_NAMES, DEFAULT_LANG, T as TEXTS
from config import (
    GROUP_CHAT_ID,
    MAX_DURATION_HOURS,
    MIN_DURATION_HOURS,
    OFFICE_CLOSE,
    OFFICE_OPEN,
    STATE_CONFIRM,
    STATE_ENTER_TITLE,
    STATE_PICK_DATE,
    STATE_PICK_DURATION,
    STATE_PICK_HOUR,
)
from services.booking_service import create_booking
from services.schedule_service import get_free_slots

logger = logging.getLogger(__name__)

# ===========================================================================
# Multi-language text dictionary
# ===========================================================================
# All user-facing strings live here. Add new keys to all 3 languages together.
# Access via: get_text(lang, "key")
# ===========================================================================


# Month names per language (used in month/day grid headers)

WEEKDAY_HEADERS: list[str] = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]



# ===========================================================================
# Helper: get localized text
# ===========================================================================

def get_text(lang: str, key: str, **kwargs) -> str:
    """
    Return the localized string for the given key and language.
    Falls back to English if the key is missing in the requested language.
    Supports keyword format substitution: get_text("en", "choose_day", month="March 2026")
    """
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(
        key,
        TEXTS[DEFAULT_LANG].get(key, f"[missing: {key}]"),
    )
    return text.format(**kwargs) if kwargs else text


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Shortcut to read the user's chosen language from context."""
    return context.user_data.get("lang", DEFAULT_LANG)


# ===========================================================================
# Booking conflict validation
# ===========================================================================

def _has_conflict(
    date_str: str,
    start_hour: int,
    duration: int,
    exclude_id: int | None = None,
) -> object | None:
    """
    Check whether [start_hour, start_hour+duration) overlaps any existing booking.

    Uses the standard overlap condition:
        requested_start < existing_end  AND  requested_end > existing_start

    Args:
        date_str:   ISO date string "YYYY-MM-DD"
        start_hour: integer hour (e.g. 15 for 15:00)
        duration:   integer hours
        exclude_id: booking id to skip (used during edits)

    Returns:
        The first conflicting Booking object, or None if the slot is free.
    """
    import database

    req_start = start_hour
    req_end   = start_hour + duration

    for b in database.get_bookings_for_date(date_str):
        if exclude_id and b.id == exclude_id:
            continue
        ex_start = int(b.start_time.split(":")[0])
        ex_end   = int(b.end_time.split(":")[0])
        # Overlap condition
        if req_start < ex_end and req_end > ex_start:
            return b
    return None


# ===========================================================================
# Keyboard builders
# ===========================================================================



def _kb_day(year: int, month: int, lang: str) -> tuple[InlineKeyboardMarkup, str]:
    """
    Full calendar grid for the given month.
    Past days: shown as number but fire cal_past (alert shown).
    Today:     shown as [N].
    Future:    shown as N.
    Padding:   shown as ' '.
    """
    today      = date.today()
    month_name = f"{MONTH_NAMES[lang][month - 1]} {year}"

    header_row = [
        InlineKeyboardButton(h, callback_data="cal_noop")
        for h in WEEKDAY_HEADERS
    ]
    rows: list[list[InlineKeyboardButton]] = [header_row]

    for week in calendar.monthcalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            else:
                d = date(year, month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(
                        str(day_num), callback_data="cal_past"
                    ))
                elif d == today:
                    row.append(InlineKeyboardButton(
                        f"[{day_num}]", callback_data=f"date:{d.isoformat()}"
                    ))
                else:
                    row.append(InlineKeyboardButton(
                        str(day_num), callback_data=f"date:{d.isoformat()}"
                    ))
        rows.append(row)

    rows.append([InlineKeyboardButton(
        get_text(lang, "back_button"),
        callback_data="back_to_month",
    )])
    rows.append([InlineKeyboardButton(
        get_text(lang, "cancel_button"),
        callback_data="book_cancel",
    )])
    return InlineKeyboardMarkup(rows), month_name


def _kb_hour(chosen_date: str, lang: str) -> InlineKeyboardMarkup:
    """
    Hour grid. Available hours fire hour:H.
    Booked hours fire hour_busy:BOOKING_ID so the alert can show
    the exact event name and time that is blocking the slot.
    4 buttons per row.
    """
    import database

    # Build a map: hour -> Booking (for every booked hour in the day)
    hour_to_booking: dict[int, object] = {}
    for b in database.get_bookings_for_date(chosen_date):
        start_h = int(b.start_time.split(":")[0])
        end_h   = int(b.end_time.split(":")[0])
        for h in range(start_h, end_h):
            hour_to_booking[h] = b

    rows: list[list[InlineKeyboardButton]] = []
    row:  list[InlineKeyboardButton] = []

    for h in range(OFFICE_OPEN, OFFICE_CLOSE):
        if h not in hour_to_booking:
            # Free slot — fully clickable
            row.append(InlineKeyboardButton(
                f"{h:02d}:00", callback_data=f"hour:{h}"
            ))
        else:
            # Booked — encode the booking id so pick_hour can fetch details
            booking_id = hour_to_booking[h].id
            row.append(InlineKeyboardButton(
                f"🔒 {h:02d}", callback_data=f"hour_busy:{booking_id}"
            ))
        if len(row) == 4:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(
        get_text(lang, "back_button"), callback_data="back_to_date"
    )])
    return InlineKeyboardMarkup(rows)


def _kb_duration(chosen_date: str, start_hour: int, lang: str) -> InlineKeyboardMarkup:
    """Duration buttons. Only shows options that fit in the next free window."""
    import datetime as _dt

    free_slots  = get_free_slots(_dt.date.fromisoformat(chosen_date))
    max_avail   = OFFICE_CLOSE - start_hour

    for slot_start, slot_end in free_slots:
        sh = int(slot_start.split(":")[0])
        eh = int(slot_end.split(":")[0])
        if sh <= start_hour < eh:
            max_avail = min(max_avail, eh - start_hour)
            break

    rows: list[list[InlineKeyboardButton]] = []
    row:  list[InlineKeyboardButton] = []

    for d in range(MIN_DURATION_HOURS, MAX_DURATION_HOURS + 1):
        if d <= max_avail:
            row.append(InlineKeyboardButton(f"{d}h", callback_data=f"dur:{d}"))
        if len(row) == 3:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    if not any(rows):
        rows = [[InlineKeyboardButton("—", callback_data="cal_noop")]]

    rows.append([InlineKeyboardButton(
        get_text(lang, "back_button"), callback_data="back_to_hour"
    )])
    return InlineKeyboardMarkup(rows)


def _kb_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "confirm_button"),      callback_data="confirm_yes"),
            InlineKeyboardButton(get_text(lang, "cancel_button"),       callback_data="book_cancel"),
        ],
        [InlineKeyboardButton(get_text(lang, "change_title_button"),    callback_data="back_to_title")],
    ])


def _kb_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "menu_button"), callback_data="menu")]
    ])


# ===========================================================================
# Language selection (called from start.py via callback lang:XX)
# ===========================================================================