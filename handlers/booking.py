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

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "start_message":       "👋 *Office Booking Bot*\n\nReserve a time slot in our shared office.\nWhat would you like to do?",
        "choose_language":     "🌐 Choose your language:",
        "book_office":         "📅 Book office",
        "choose_month":        "📅 *Step 1 of 4 — Choose a month:*",
        "choose_day":          "📅 *{month}* — choose a day:",
        "choose_time":         "📅 {date}\n\n🕐 *Step 2 of 4 — Choose start time:*",
        "choose_duration":     "📅 {date}  |  🕐 {hour}:00\n\n⏱ *Step 3 of 4 — Choose duration:*",
        "enter_title":         "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}h\n\n✏️ *Step 4 of 4 — Enter event title:*\n\n_Type the name of your event (e.g. Board Games, Team Meeting)_",
        "enter_title_again":   "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}h\n\n✏️ *Step 4 of 4 — Enter event title:*\n\n_Type the name of your event_",
        "confirm_preview":     "✅ *Confirm your booking:*\n\n📋 *{title}*\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}h)\n👤 @{user}",
        "booking_confirmed":   "🎉 *Booking confirmed!*\n\n{details}",
        "booking_conflict":    "❌ *Time slot already booked!*\n\nThis time overlaps with:\n\n🕐 {start} – {end}\n📋 *{title}*\n👤 @{user}\n\nPlease choose a different time.",
        "booking_cancelled":   "Booking cancelled.",
        "no_bookings_today":   "📭 No bookings for this day.",
        "slot_taken_alert":    "⛔ This hour is already booked.",
        "title_too_long":      "Title is too long ({length} chars). Max 80 characters — please shorten it.",
        "title_empty":         "Please enter a title for your event.",
        "back_button":         "←  Back",
        "cancel_button":       "✖  Cancel",
        "confirm_button":      "✅  Confirm",
        "menu_button":         "←  Menu",
        "change_title_button": "←  Change title",
        "error_message":       "Something went wrong. Please try again.",
        "past_day_alert":      "That day is already in the past.",
        "group_notification":  "📢 *New office booking*\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 *{title}*\n👤 Organiser: @{user}",
    },
    "ru": {
        "start_message":       "👋 *Бот бронирования офиса*\n\nЗабронируйте время в нашем общем офисе.\nЧто вы хотите сделать?",
        "choose_language":     "🌐 Выберите язык:",
        "book_office":         "📅 Забронировать офис",
        "choose_month":        "📅 *Шаг 1 из 4 — Выберите месяц:*",
        "choose_day":          "📅 *{month}* — выберите день:",
        "choose_time":         "📅 {date}\n\n🕐 *Шаг 2 из 4 — Выберите время начала:*",
        "choose_duration":     "📅 {date}  |  🕐 {hour}:00\n\n⏱ *Шаг 3 из 4 — Выберите длительность:*",
        "enter_title":         "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ч\n\n✏️ *Шаг 4 из 4 — Введите название события:*\n\n_Например: Настольные игры, Встреча команды_",
        "enter_title_again":   "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ч\n\n✏️ *Шаг 4 из 4 — Введите название события:*\n\n_Введите название_",
        "confirm_preview":     "✅ *Подтвердите бронирование:*\n\n📋 *{title}*\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}ч)\n👤 @{user}",
        "booking_confirmed":   "🎉 *Бронирование подтверждено!*\n\n{details}",
        "booking_conflict":    "❌ *Это время уже занято!*\n\nПересечение с существующей записью:\n\n🕐 {start} – {end}\n📋 *{title}*\n👤 @{user}\n\nПожалуйста, выберите другое время.",
        "booking_cancelled":   "Бронирование отменено.",
        "no_bookings_today":   "📭 На этот день бронирований нет.",
        "slot_taken_alert":    "⛔ Этот час уже занят.",
        "title_too_long":      "Название слишком длинное ({length} символов). Максимум 80 — сократите, пожалуйста.",
        "title_empty":         "Пожалуйста, введите название события.",
        "back_button":         "←  Назад",
        "cancel_button":       "✖  Отмена",
        "confirm_button":      "✅  Подтвердить",
        "menu_button":         "←  Меню",
        "change_title_button": "←  Изменить название",
        "error_message":       "Что-то пошло не так. Попробуйте ещё раз.",
        "past_day_alert":      "Этот день уже прошёл.",
        "group_notification":  "📢 *Новое бронирование офиса*\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 *{title}*\n👤 Организатор: @{user}",
    },
    "hy": {
        "start_message":       "👋 *Օֆիսի ամրագրման բոտ*\n\nՊահպանեք ժամաֆաիկ մեր ընդհանուր օֆիսում։\nԻնչ կցանկանայի՞ք անել:",
        "choose_language":     "🌐 Ընտրեք լեզուն:",
        "book_office":         "📅 Ամրագրել օֆիս",
        "choose_month":        "📅 *Քայլ 1 4-ից — Ընտրեք ամիսը:*",
        "choose_day":          "📅 *{month}* — ընտրեք օրը:",
        "choose_time":         "📅 {date}\n\n🕐 *Քայլ 2 4-ից — Ընտրեք մեկնարկի ժամը:*",
        "choose_duration":     "📅 {date}  |  🕐 {hour}:00\n\n⏱ *Քայլ 3 4-ից — Ընտրեք տևողությունը:*",
        "enter_title":         "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ժ\n\n✏️ *Քայլ 4 4-ից — Մուտքագրեք միջոցառման անունը:*\n\n_Օրինակ՝ Սեղանի խաղեր, Թիմային հանդիպում_",
        "enter_title_again":   "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ժ\n\n✏️ *Քայլ 4 4-ից — Մուտքագրեք միջոցառման անունը:*\n\n_Մուտքագրեք անունը_",
        "confirm_preview":     "✅ *Հաստատե՞լ ամրագրումը:*\n\n📋 *{title}*\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}ժ)\n👤 @{user}",
        "booking_confirmed":   "🎉 *Ամրագրումը հաստատված է!*\n\n{details}",
        "booking_conflict":    "❌ *Այս ժամը արդեն զբաղված է!*\n\nՀատվածություն կա հետևյալ ամրագրման հետ.\n\n🕐 {start} – {end}\n📋 *{title}*\n👤 @{user}\n\nԽնդրում ենք ընտրել այլ ժամ։",
        "booking_cancelled":   "Ամրագրումը չեղարկված է։",
        "no_bookings_today":   "📭 Այս օրվա համար ամրագրումներ չկան։",
        "slot_taken_alert":    "⛔ Այս ժամը արդեն զբաղված է։",
        "title_too_long":      "Անունը շատ երկար է ({length} նիշ)։ Առավելագույնը 80 նիշ։",
        "title_empty":         "Խնդրում ենք մուտքագրել միջոցառման անունը։",
        "back_button":         "←  Հետ",
        "cancel_button":       "✖  Չեղարկել",
        "confirm_button":      "✅  Հաստատել",
        "menu_button":         "←  Մենյու",
        "change_title_button": "←  Փոխել անունը",
        "error_message":       "Ինչ-որ բան սխալ գնաց։ Խնդրում ենք փորձել կրկին։",
        "past_day_alert":      "Այդ օրն արդեն անցել է։",
        "group_notification":  "📢 *Օֆիսի նոր ամրագրում*\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 *{title}*\n👤 Կազմակերպիչ: @{user}",
    },
}

# Month names per language (used in month/day grid headers)
MONTH_NAMES: dict[str, list[str]] = {
    "en": ["January","February","March","April","May","June",
           "July","August","September","October","November","December"],
    "ru": ["Январь","Февраль","Март","Апрель","Май","Июнь",
           "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],
    "hy": ["Հունվար","Փետրվար","Մարտ","Ապրիլ","Մայիս","Հունիս",
           "Հուլիս","Օգոստոս","Սեպտեմբեր","Հոկտեմբեր","Նոյեմբեր","Դեկտեմբեր"],
}

WEEKDAY_HEADERS: list[str] = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

DEFAULT_LANG = "en"


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

def _kb_language() -> InlineKeyboardMarkup:
    """Language selection keyboard shown at /start."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧  English",   callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺  Русский",   callback_data="lang:ru")],
        [InlineKeyboardButton("🇦🇲  Հայերեն",  callback_data="lang:hy")],
    ])


def _kb_month(lang: str) -> InlineKeyboardMarkup:
    """
    Rolling 12-month grid starting from the current month.
    3 months per row. No year step needed.
    """
    today  = date.today()
    rows:  list[list[InlineKeyboardButton]] = []
    row:   list[InlineKeyboardButton] = []
    names  = MONTH_NAMES[lang]

    for i in range(12):
        # Calculate which month this slot represents
        total_month = today.month - 1 + i       # 0-based offset
        year  = today.year + total_month // 12
        month = total_month % 12 + 1
        label = f"{names[month - 1][:3]} {str(year)[2:]}"   # e.g. "Mar 26"
        row.append(InlineKeyboardButton(
            label,
            callback_data=f"cal_month:{year}:{month}",
        ))
        if len(row) == 3:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(
        get_text(lang, "cancel_button"),
        callback_data="book_cancel",
    )])
    return InlineKeyboardMarkup(rows)


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

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Store the selected language in user_data and show the main menu.
    Triggered by callback_data="lang:en" / "lang:ru" / "lang:hy".
    Registered as a plain CallbackQueryHandler in start.py.
    """
    query = update.callback_query
    await query.answer()

    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang

    from handlers.start import _main_menu_keyboard
    await query.edit_message_text(
        get_text(lang, "start_message"),
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(lang),
    )


# ===========================================================================
# Step 1 — Entry: show month grid (year step removed)
# ===========================================================================

async def book_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point. Clears booking state and shows the month picker directly.
    Year selection has been removed — months roll forward 12 months from today.
    """
    query = update.callback_query
    await query.answer()

    # Preserve language; clear everything else
    lang = _lang(context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    await query.edit_message_text(
        get_text(lang, "choose_month"),
        parse_mode="Markdown",
        reply_markup=_kb_month(lang),
    )
    return STATE_PICK_DATE


# ===========================================================================
# Step 1b — Month chosen: show day grid
# ===========================================================================

async def pick_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store year+month and show the full calendar day grid."""
    query = update.callback_query
    await query.answer()

    _, year_str, month_str = query.data.split(":")
    year  = int(year_str)
    month = int(month_str)
    lang  = _lang(context)

    context.user_data["cal_year"]  = year
    context.user_data["cal_month"] = month

    keyboard, month_label = _kb_day(year, month, lang)
    await query.edit_message_text(
        get_text(lang, "choose_day", month=month_label),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return STATE_PICK_DATE


async def back_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate back to the month grid."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    await query.edit_message_text(
        get_text(lang, "choose_month"),
        parse_mode="Markdown",
        reply_markup=_kb_month(lang),
    )
    return STATE_PICK_DATE


# ===========================================================================
# Step 1 final — Day chosen: show hour picker
# ===========================================================================

async def pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store chosen date and show the hour picker."""
    query = update.callback_query
    await query.answer()

    chosen_date: str = query.data.split(":")[1]
    lang = _lang(context)
    context.user_data["date"] = chosen_date

    await query.edit_message_text(
        get_text(lang, "choose_time", date=chosen_date),
        parse_mode="Markdown",
        reply_markup=_kb_hour(chosen_date, lang),
    )
    return STATE_PICK_HOUR


async def back_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate back to the day grid from the hour picker."""
    query = update.callback_query
    await query.answer()

    lang  = _lang(context)
    year  = context.user_data.get("cal_year")
    month = context.user_data.get("cal_month")

    if year and month:
        keyboard, month_label = _kb_day(year, month, lang)
        await query.edit_message_text(
            get_text(lang, "choose_day", month=month_label),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await query.edit_message_text(
            get_text(lang, "choose_month"),
            parse_mode="Markdown",
            reply_markup=_kb_month(lang),
        )
    return STATE_PICK_DATE


# ---------------------------------------------------------------------------
# Calendar no-op handlers
# ---------------------------------------------------------------------------

async def cal_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Silently absorb taps on header / padding cells."""
    await update.callback_query.answer()
    return STATE_PICK_DATE


async def cal_past(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Alert when user taps a past day."""
    lang = _lang(context)
    await update.callback_query.answer(
        get_text(lang, "past_day_alert"),
        show_alert=True,
    )
    return STATE_PICK_DATE


# ===========================================================================
# Step 2 — Hour chosen
# ===========================================================================

async def pick_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Store chosen hour and show duration options.
    If hour is already booked, fetches the booking details and shows a
    descriptive alert: event name, organiser, and time range.
    callback_data formats:
        "hour:15"          -- free slot, proceed
        "hour_busy:42"     -- booked, 42 is the booking id
    """
    query = update.callback_query
    lang  = _lang(context)

    if query.data.startswith("hour_busy"):
        import database
        try:
            booking_id = int(query.data.split(":")[1])
            b = database.get_booking_by_id(booking_id)
            if b:
                alert = (
                    "🔒 Already booked!\n\n"
                    f"📋 {b.title}\n"
                    f"🕐 {b.start_time} - {b.end_time}\n"
                    f"👤 @{b.username}"
                )
            else:
                alert = get_text(lang, "slot_taken_alert")
        except (IndexError, ValueError):
            alert = get_text(lang, "slot_taken_alert")

        await query.answer(alert, show_alert=True)
        return STATE_PICK_HOUR

    await query.answer()
    hour: int        = int(query.data.split(":")[1])
    chosen_date: str = context.user_data["date"]
    context.user_data["start_hour"] = hour

    await query.edit_message_text(
        get_text(lang, "choose_duration", date=chosen_date, hour=f"{hour:02d}"),
        parse_mode="Markdown",
        reply_markup=_kb_duration(chosen_date, hour, lang),
    )
    return STATE_PICK_DURATION


async def back_to_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate back to hour picker from duration screen."""
    query = update.callback_query
    await query.answer()

    lang        = _lang(context)
    chosen_date = context.user_data["date"]

    await query.edit_message_text(
        get_text(lang, "choose_time", date=chosen_date),
        parse_mode="Markdown",
        reply_markup=_kb_hour(chosen_date, lang),
    )
    return STATE_PICK_HOUR


# ===========================================================================
# Step 3 — Duration chosen
# ===========================================================================

async def pick_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store duration and prompt for event title."""
    query = update.callback_query
    await query.answer()

    duration: int    = int(query.data.split(":")[1])
    lang             = _lang(context)
    chosen_date: str = context.user_data["date"]
    start_hour: int  = context.user_data["start_hour"]

    context.user_data["duration"] = duration

    await query.edit_message_text(
        get_text(lang, "enter_title",
                 date=chosen_date,
                 hour=f"{start_hour:02d}",
                 duration=duration),
        parse_mode="Markdown",
    )
    return STATE_ENTER_TITLE


async def back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate back to title prompt from confirm screen."""
    query = update.callback_query
    await query.answer()

    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    start_hour  = context.user_data["start_hour"]
    duration    = context.user_data["duration"]

    await query.edit_message_text(
        get_text(lang, "enter_title_again",
                 date=chosen_date,
                 hour=f"{start_hour:02d}",
                 duration=duration),
        parse_mode="Markdown",
    )
    return STATE_ENTER_TITLE


# ===========================================================================
# Step 4 — Title entered
# ===========================================================================

async def enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate title and show booking preview."""
    title: str = update.message.text.strip()
    lang       = _lang(context)

    if not title:
        await update.message.reply_text(get_text(lang, "title_empty"))
        return STATE_ENTER_TITLE

    if len(title) > 80:
        await update.message.reply_text(
            get_text(lang, "title_too_long", length=len(title))
        )
        return STATE_ENTER_TITLE

    context.user_data["title"] = title

    chosen_date:  str = context.user_data["date"]
    start_hour:   int = context.user_data["start_hour"]
    duration:     int = context.user_data["duration"]
    end_hour:     int = start_hour + duration
    display_name: str = (
        update.effective_user.username or update.effective_user.first_name
    )

    preview = get_text(
        lang, "confirm_preview",
        title    = title,
        date     = chosen_date,
        start    = f"{start_hour:02d}",
        end      = f"{end_hour:02d}",
        duration = duration,
        user     = display_name,
    )
    await update.message.reply_text(
        preview,
        parse_mode="Markdown",
        reply_markup=_kb_confirm(lang),
    )
    return STATE_CONFIRM


# ===========================================================================
# Confirm
# ===========================================================================

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Validate the slot one final time then create the booking.

    Validation uses _has_conflict() which applies the standard overlap check:
        requested_start < existing_end  AND  requested_end > existing_start

    On conflict → show details of the clashing booking.
    On success  → confirm + optional group notification.
    """
    query = update.callback_query
    await query.answer()

    lang         = _lang(context)
    user         = update.effective_user
    username     = user.username or user.first_name
    ud           = context.user_data
    start_hour   = ud["start_hour"]
    duration     = ud["duration"]

    # ── Final conflict check before writing to DB ─────────────────────────
    conflict = _has_conflict(ud["date"], start_hour, duration)
    if conflict:
        await query.edit_message_text(
            get_text(
                lang, "booking_conflict",
                start = conflict.start_time,
                end   = conflict.end_time,
                title = conflict.title,
                user  = conflict.username,
            ),
            parse_mode="Markdown",
            reply_markup=_kb_menu(lang),
        )
        return ConversationHandler.END

    # ── Create booking ────────────────────────────────────────────────────
    start_time = f"{start_hour:02d}:00"
    new_booking, db_conflict = create_booking(
        user_id    = user.id,
        username   = username,
        title      = ud["title"],
        date       = ud["date"],
        start_time = start_time,
        duration   = duration,
    )

    # Edge case: race condition — someone booked in the split second between
    # the check above and the DB write
    if db_conflict:
        await query.edit_message_text(
            get_text(
                lang, "booking_conflict",
                start = db_conflict.start_time,
                end   = db_conflict.end_time,
                title = db_conflict.title,
                user  = db_conflict.username,
            ),
            parse_mode="Markdown",
            reply_markup=_kb_menu(lang),
        )
        return ConversationHandler.END

    # ── Success ───────────────────────────────────────────────────────────
    await query.edit_message_text(
        get_text(lang, "booking_confirmed", details=new_booking.full_text()),
        parse_mode="Markdown",
        reply_markup=_kb_menu(lang),
    )

    # ── Group notification ────────────────────────────────────────────────
    if GROUP_CHAT_ID:
        import datetime as _dt
        day_name = _dt.date.fromisoformat(new_booking.date).strftime("%A, %b %d")
        # Group notifications always in English
        notification = get_text(
            "en", "group_notification",
            day   = day_name,
            start = new_booking.start_time,
            end   = new_booking.end_time,
            title = new_booking.title,
            user  = new_booking.username,
        )
        try:
            await context.bot.send_message(
                chat_id    = GROUP_CHAT_ID,
                text       = notification,
                parse_mode = "Markdown",
            )
        except Exception as exc:
            logger.warning("Group notification failed: %s", exc)

    context.user_data.clear()
    return ConversationHandler.END


# ===========================================================================
# Cancel — available at any step
# ===========================================================================

async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the booking flow and return to the main menu."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    context.user_data.clear()

    await query.edit_message_text(
        get_text(lang, "booking_cancelled"),
        reply_markup=_kb_menu(lang),
    )
    return ConversationHandler.END


# ===========================================================================
# Handler registration
# ===========================================================================

def register(application) -> None:
    """Register the booking ConversationHandler and language selector."""
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(book_entry, pattern="^book$"),
        ],
        states={
            STATE_PICK_DATE: [
                CallbackQueryHandler(pick_month,    pattern=r"^cal_month:\d+:\d+$"),
                CallbackQueryHandler(pick_date,     pattern=r"^date:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(back_to_month, pattern="^back_to_month$"),
                CallbackQueryHandler(cal_noop,      pattern="^cal_noop$"),
                CallbackQueryHandler(cal_past,      pattern="^cal_past$"),
                CallbackQueryHandler(book_cancel,   pattern="^book_cancel$"),
            ],
            STATE_PICK_HOUR: [
                CallbackQueryHandler(pick_hour,    pattern=r"^hour:\d+$"),
                CallbackQueryHandler(pick_hour,    pattern=r"^hour_busy:\d+$"),
                CallbackQueryHandler(back_to_date, pattern="^back_to_date$"),
                CallbackQueryHandler(book_cancel,  pattern="^book_cancel$"),
            ],
            STATE_PICK_DURATION: [
                CallbackQueryHandler(pick_duration, pattern=r"^dur:\d+$"),
                CallbackQueryHandler(back_to_hour,  pattern="^back_to_hour$"),
                CallbackQueryHandler(book_cancel,   pattern="^book_cancel$"),
            ],
            STATE_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_title),
                CallbackQueryHandler(book_cancel, pattern="^book_cancel$"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(confirm_booking, pattern="^confirm_yes$"),
                CallbackQueryHandler(back_to_title,   pattern="^back_to_title$"),
                CallbackQueryHandler(book_cancel,     pattern="^book_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(book_cancel, pattern="^book_cancel$"),
        ],
        per_message=False,
    )
    application.add_handler(conv)

    # Language picker — registered outside the conversation so it works
    # from the /start screen before any booking flow begins
    application.add_handler(
        CallbackQueryHandler(set_language, pattern=r"^lang:(en|ru|hy)$")
    )