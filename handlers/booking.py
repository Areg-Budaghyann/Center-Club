"""
handlers/booking.py — FULL REPLACEMENT
Slot-based time picker with 5-minute intervals and pagination.

Flow: Date → Start slot (paginated) → End slot (paginated) → Title → Confirm
"""

import calendar
import logging
from datetime import date, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

from config import (
    ADMIN_IDS, GROUP_CHAT_ID, MAX_DURATION_HOURS,
    OFFICE_CLOSE, OFFICE_OPEN,
    STATE_PICK_DATE, STATE_PICK_START, STATE_PICK_END,
    STATE_ENTER_TITLE, STATE_CONFIRM,
)
from translations import MONTH_SHORT
from services.booking_service import create_booking
from translations import WEEKDAY_HEADERS, get_text
from scheduler.log_bot import log_booking

logger = logging.getLogger(__name__)

# ── Time picker config ────────────────────────────────────────────────────────
MINUTE_STEPS = [0, 15, 30, 45]  # minute options shown after hour is chosen



# ── Helpers ───────────────────────────────────────────────────────────────────

def _lang(context) -> str:
    return context.user_data.get("lang", "en")


def _display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    parts = [user.first_name or "", user.last_name or ""]
    return " ".join(p for p in parts if p).strip() or str(user.id)


def _time_to_min(t: str) -> int:
    """'08:30' → 510"""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _min_to_time(m: int) -> str:
    """510 → '08:30'"""
    return f"{m // 60:02d}:{m % 60:02d}"


def _booked_ranges(chosen_date: str) -> list:
    """Return list of (start_min, end_min) for existing bookings."""
    import database
    ranges = []
    for b in database.get_bookings_for_date(chosen_date):
        ranges.append((_time_to_min(b.start_time), _time_to_min(b.end_time)))
    return ranges


def _hour_available(hour: int, chosen_date: str, booked: list) -> bool:
    """True if any minute in this hour is bookable (not fully booked)."""
    hour_start = hour * 60
    hour_end   = hour_start + 60
    for bs, be in booked:
        if bs <= hour_start and be >= hour_end:
            return False  # entire hour blocked
    return True


def _kb_hours(chosen_date: str, lang: str) -> InlineKeyboardMarkup:
    """Show all 24 hours in a 4-column grid. Lock fully-booked hours."""
    booked = _booked_ranges(chosen_date)
    rows, row = [], []
    for h in range(OFFICE_OPEN, OFFICE_CLOSE):
        label = f"{h:02d}:xx"
        if _hour_available(h, chosen_date, booked):
            row.append(InlineKeyboardButton(label, callback_data=f"hour:{h}"))
        else:
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_date")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_minutes(hour: int, chosen_date: str, lang: str) -> InlineKeyboardMarkup:
    """Show minute options for chosen hour. Lock conflicting minutes."""
    booked = _booked_ranges(chosen_date)
    row = []
    for m in MINUTE_STEPS:
        slot_min = hour * 60 + m
        # Check if this start slot is already booked
        blocked = any(bs <= slot_min < be for bs, be in booked)
        label = f"{hour:02d}:{m:02d}"
        if blocked:
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f"start:{slot_min}"))
    rows = [row]
    rows.append([InlineKeyboardButton(f"← {get_text(lang, 'btn_back')}", callback_data="back_to_hours")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_end_hours(chosen_date: str, start_min: int, lang: str) -> InlineKeyboardMarkup:
    """Hour grid for end time — only shows hours after start."""
    booked = _booked_ranges(chosen_date)
    start_hour = start_min // 60

    # Find first blocking booking after start
    first_block_hour = OFFICE_CLOSE
    for bs, be in booked:
        if bs > start_min:
            first_block_hour = min(first_block_hour, bs // 60)

    rows, row = [], []
    for h in range(start_hour, OFFICE_CLOSE):
        label = f"{h:02d}:xx"
        if h > first_block_hour:
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f"end_hour:{h}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not rows:
        rows = [[InlineKeyboardButton("—", callback_data="slot_busy")]]
    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_start")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_end_minutes(hour: int, chosen_date: str, start_min: int, lang: str) -> InlineKeyboardMarkup:
    """Minute options for end time. Only shows times strictly after start."""
    booked = _booked_ranges(chosen_date)
    row = []
    for m in MINUTE_STEPS:
        slot_min = hour * 60 + m
        if slot_min <= start_min:
            row.append(InlineKeyboardButton("—", callback_data="slot_busy"))
            continue
        # Check conflict
        blocked = any(start_min < be <= slot_min and bs < slot_min for bs, be in booked)
        label = f"{hour:02d}:{m:02d}"
        if blocked:
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        else:
            row.append(InlineKeyboardButton(label, callback_data=f"end:{slot_min}"))
    rows = [row]
    rows.append([InlineKeyboardButton(f"← {get_text(lang, 'btn_back')}", callback_data="back_to_end_hours")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows)



def _has_conflict_range(date_str: str, start_min: int, end_min: int, exclude_id=None):
    """Return conflicting booking or None."""
    import database
    for b in database.get_bookings_for_date(date_str):
        if exclude_id and b.id == exclude_id:
            continue
        bs = _time_to_min(b.start_time)
        be = _time_to_min(b.end_time)
        if start_min < be and end_min > bs:
            return b
    return None


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _kb_month(lang: str) -> InlineKeyboardMarkup:
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"cal_month:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_day(year: int, month: int, lang: str):
    today       = date.today()
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"
    headers     = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    rows = [[InlineKeyboardButton(h, callback_data="cal_noop") for h in headers]]

    # Get event dates for this month
    try:
        import database as _db
        event_dicts = _db.get_special_events_for_month(year, month)
        event_dates = set()
        for ev in event_dicts:
            parts = ev["event_date"].replace(" ", "").split("–")
            if len(parts) == 2:
                try:
                    s = date.fromisoformat(parts[0])
                    e = date.fromisoformat(parts[1])
                    cur = s
                    while cur <= e:
                        event_dates.add(cur.isoformat())
                        cur = date.fromordinal(cur.toordinal() + 1)
                except Exception:
                    pass
            else:
                event_dates.add(ev["event_date"].strip())
    except Exception:
        event_dates = set()

    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            else:
                d = date(year, month, day_num)
                has_ev = d.isoformat() in event_dates
                if d < today:
                    row.append(InlineKeyboardButton(str(day_num), callback_data="cal_past"))
                elif d == today:
                    label = f"[{day_num}]🎉" if has_ev else f"[{day_num}]"
                    row.append(InlineKeyboardButton(label, callback_data=f"date:{d.isoformat()}"))
                else:
                    label = f"{day_num}🎉" if has_ev else str(day_num)
                    row.append(InlineKeyboardButton(label, callback_data=f"date:{d.isoformat()}"))
        rows.append(row)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_month")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows), month_label


def _kb_start_slots(chosen_date: str, page: int, lang: str) -> tuple[InlineKeyboardMarkup, str]:
    """
    Paginated start-time slot picker.
    Returns (keyboard, header_text).
    """
    all_slots  = _all_slots()
    booked     = _booked_minutes(chosen_date)
    total_pages = max(1, (len(all_slots) + PAGE_SIZE - 1) // PAGE_SIZE)
    page       = max(0, min(page, total_pages - 1))

    page_slots = all_slots[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    first_time = _min_to_time(page_slots[0])  if page_slots else "—"
    last_time  = _min_to_time(page_slots[-1]) if page_slots else "—"
    header = f"🕐 {first_time} – {last_time}  ({page + 1}/{total_pages})"

    rows, row = [], []
    for slot in page_slots:
        t = _min_to_time(slot)
        if slot in booked:
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        else:
            row.append(InlineKeyboardButton(t, callback_data=f"start:{slot}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Earlier", callback_data=f"start_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Later →", callback_data=f"start_page:{page + 1}"))
    if nav:
        rows.append(nav)

    # Quick-jump row
    qj = _quick_jump_row(total_pages, all_slots)
    if qj:
        rows.append(qj)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_date")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows), header


def _kb_end_slots(chosen_date: str, start_min: int, page: int, lang: str) -> tuple[InlineKeyboardMarkup, str]:
    """
    Paginated end-time slot picker.
    Only shows times strictly after start_min.
    Locks slots that would create a conflict.
    """
    import database
    all_slots   = [s for s in _all_slots() if s > start_min]
    booked_raw  = database.get_bookings_for_date(chosen_date)

    # Find the first conflicting booking after start — cap end slots there
    first_block = None
    for b in sorted(booked_raw, key=lambda x: _time_to_min(x.start_time)):
        bs = _time_to_min(b.start_time)
        if bs > start_min:
            first_block = bs
            break

    total_pages = max(1, (len(all_slots) + PAGE_SIZE - 1) // PAGE_SIZE)
    page       = max(0, min(page, total_pages - 1))
    page_slots = all_slots[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    first_time = _min_to_time(page_slots[0])  if page_slots else "—"
    last_time  = _min_to_time(page_slots[-1]) if page_slots else "—"
    header = f"🕐 {first_time} – {last_time}  ({page + 1}/{total_pages})"

    rows, row = [], []
    for slot in page_slots:
        t = _min_to_time(slot)
        if first_block is not None and slot > first_block:
            # Can't book past an existing booking
            row.append(InlineKeyboardButton("🔒", callback_data="slot_busy"))
        else:
            row.append(InlineKeyboardButton(t, callback_data=f"end:{slot}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Earlier", callback_data=f"end_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Later →", callback_data=f"end_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_start")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows), header


def _kb_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "btn_confirm"), callback_data="confirm_yes"),
            InlineKeyboardButton(get_text(lang, "btn_cancel"),  callback_data="book_cancel"),
        ],
        [InlineKeyboardButton(get_text(lang, "btn_change_title"), callback_data="back_to_title")],
    ])


def _kb_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]
    ])


# ── Step 1 — Entry / Month ────────────────────────────────────────────────────

async def book_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    menu_msg_id = context.bot_data.get("menu_msgs", {}).get(update.effective_user.id)
    await _clear_notifications(context.bot, update.effective_user.id, context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    await query.edit_message_text(
        get_text(lang, "choose_month"),
        reply_markup=_kb_month(lang),
    )
    return STATE_PICK_DATE


async def pick_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, year_str, month_str = query.data.split(":")
    year, month = int(year_str), int(month_str)
    lang = _lang(context)
    context.user_data["cal_year"]  = year
    context.user_data["cal_month"] = month
    keyboard, month_label = _kb_day(year, month, lang)
    await query.edit_message_text(
        f"📅 {month_label}",
        reply_markup=keyboard,
    )
    return STATE_PICK_DATE


async def back_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(
        get_text(lang, "choose_month"),
        reply_markup=_kb_month(lang),
    )
    return STATE_PICK_DATE


async def pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.split(":")[1]
    lang = _lang(context)
    context.user_data["date"] = chosen_date
    context.user_data["start_page"] = 0

    # Jump to first available page
    booked = _booked_minutes(chosen_date)
    all_s  = _all_slots()
    # Find page that has at least one free slot
    page = 0
    now_min = datetime.now().hour * 60 + datetime.now().minute
    if chosen_date == date.today().isoformat():
        # Start on page containing current time
        for i, s in enumerate(all_s):
            if s >= now_min:
                page = i // PAGE_SIZE
                break

    context.user_data["start_page"] = page
    kb, header = _kb_start_slots(chosen_date, page, lang)

    # Show special events notice if any
    try:
        import database as _db2
        day_events = [e for e in _db2.get_all_special_events()
                      if _date_in_event_range(chosen_date, e["event_date"])]
        event_notice = ""
        if day_events:
            event_notice = "\n\n🎉 " + "\n🎉 ".join(
                f"{e['title']} ({e['event_date']})" for e in day_events
            )
    except Exception:
        event_notice = ""

    await query.edit_message_text(
        f"📅 {chosen_date}{event_notice}\n\n{header}\n\n{get_text(lang, 'choose_start_time')}",
        reply_markup=kb,
    )
    return STATE_PICK_START


async def back_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data.get("cal_year")
    month = context.user_data.get("cal_month")
    if year and month:
        keyboard, month_label = _kb_day(year, month, lang)
        await query.edit_message_text(f"📅 {month_label}", reply_markup=keyboard)
    else:
        await query.edit_message_text(get_text(lang, "choose_month"), reply_markup=_kb_month(lang))
    return STATE_PICK_DATE


async def cal_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return STATE_PICK_DATE


async def cal_past(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    await update.callback_query.answer(get_text(lang, "past_day_alert"), show_alert=True)
    return STATE_PICK_DATE


# ── Step 2 — Start time ───────────────────────────────────────────────────────

async def start_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate start slot pages."""
    query = update.callback_query
    await query.answer()
    lang        = _lang(context)
    page        = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    context.user_data["start_page"] = page

    kb, header = _kb_start_slots(chosen_date, page, lang)
    await query.edit_message_text(
        f"📅 {chosen_date}\n\n{header}\n\n{get_text(lang, 'choose_start_time')}",
        reply_markup=kb,
    )
    return STATE_PICK_START



async def pick_hour_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped a start hour - show minute options for that hour."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    hour        = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    context.user_data["pending_hour"] = hour
    kb = _kb_minutes(hour, chosen_date, lang)
    await query.edit_message_text(
        get_text(lang, "choose_start_time") + " " + str(hour).zfill(2) + ":__",
        reply_markup=kb,
    )
    return STATE_PICK_START


async def back_to_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Back from minute picker to hour grid."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    kb = _kb_hours(chosen_date, lang)
    await query.edit_message_text(
        get_text(lang, "choose_start_time"),
        reply_markup=kb,
    )
    return STATE_PICK_START



async def pick_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User selected start minute - show end hour grid."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    start_min   = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    start_time  = _min_to_time(start_min)
    context.user_data["start_min"]  = start_min
    context.user_data["start_time"] = start_time
    kb = _kb_end_hours(chosen_date, start_min, lang)
    msg = (get_text(lang, "start_label") + ": " + start_time
           + chr(10) + chr(10) + get_text(lang, "choose_end_time"))
    await query.edit_message_text(msg, reply_markup=kb)
    return STATE_PICK_END


async def pick_hour_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped end hour - show minute options."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    hour        = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    start_min   = context.user_data["start_min"]
    start_time  = context.user_data["start_time"]
    context.user_data["pending_end_hour"] = hour
    kb  = _kb_end_minutes(hour, chosen_date, start_min, lang)
    msg = (get_text(lang, "start_label") + ": " + start_time
           + chr(10) + f"{hour:02d}:__ - " + get_text(lang, "choose_end_time"))
    await query.edit_message_text(msg, reply_markup=kb)
    return STATE_PICK_END


async def back_to_end_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Back from end-minute to end-hour grid."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    start_min   = context.user_data["start_min"]
    start_time  = context.user_data["start_time"]
    kb  = _kb_end_hours(chosen_date, start_min, lang)
    msg = (get_text(lang, "start_label") + ": " + start_time
           + chr(10) + chr(10) + get_text(lang, "choose_end_time"))
    await query.edit_message_text(msg, reply_markup=kb)
    return STATE_PICK_END


async def slot_busy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    await update.callback_query.answer(get_text(lang, "slot_taken_alert"), show_alert=True)
    return context.user_data.get("_state", STATE_PICK_START)


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Back from end hour grid to start hour grid."""
    query       = update.callback_query
    await query.answer()
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    kb = _kb_hours(chosen_date, lang)
    await query.edit_message_text(get_text(lang, "choose_start_time"), reply_markup=kb)
    return STATE_PICK_START


async def end_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate end slot pages."""
    query = update.callback_query
    await query.answer()
    lang        = _lang(context)
    page        = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    start_min   = context.user_data["start_min"]
    start_time  = context.user_data["start_time"]
    context.user_data["end_page"] = page

    kb, header = _kb_end_slots(chosen_date, start_min, page, lang)
    await query.edit_message_text(
        f"📅 {chosen_date}\n"
        f"▶️ {get_text(lang, 'start_label')}: {start_time}\n\n"
        f"{header}\n\n{get_text(lang, 'choose_end_time')}",
        reply_markup=kb,
    )
    return STATE_PICK_END


async def pick_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User selected end time slot."""
    query = update.callback_query
    await query.answer()
    lang        = _lang(context)
    end_min     = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    start_min   = context.user_data["start_min"]
    start_time  = context.user_data["start_time"]

    if end_min <= start_min:
        await query.answer(get_text(lang, "end_before_start_alert"), show_alert=True)
        return STATE_PICK_END

    end_time = _min_to_time(end_min)
    context.user_data["end_min"]  = end_min
    context.user_data["end_time"] = end_time

    # Compute duration string
    dur_min = end_min - start_min
    h, m = divmod(dur_min, 60)
    h_suf = {"en": "h", "ru": "ч", "hy": "ժ"}.get(lang, "h")
    m_suf = {"en": "m", "ru": "м", "hy": "ր"}.get(lang, "m")
    if h > 0 and m > 0:
        dur_str = f"{h}{h_suf} {m}{m_suf}"
    elif h > 0:
        dur_str = f"{h}{h_suf}"
    else:
        dur_str = f"{m}{m_suf}"

    context.user_data["dur_str"] = dur_str

    # Show title prompt
    back_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_end")
    ]])
    msg = await query.edit_message_text(
        get_text(lang, "enter_title",
                 date=chosen_date,
                 hour=start_time,
                 duration=dur_str),
        reply_markup=back_kb,
    )
    context.user_data["title_prompt_msg_id"] = msg.message_id
    return STATE_ENTER_TITLE


async def back_to_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Back from title to end picker."""
    query = update.callback_query
    await query.answer()
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    start_min   = context.user_data["start_min"]
    start_time  = context.user_data["start_time"]
    page        = context.user_data.get("end_page", 0)

    kb, header = _kb_end_slots(chosen_date, start_min, page, lang)
    await query.edit_message_text(
        f"📅 {chosen_date}\n"
        f"▶️ {get_text(lang, 'start_label')}: {start_time}\n\n"
        f"{header}\n\n{get_text(lang, 'choose_end_time')}",
        reply_markup=kb,
    )
    return STATE_PICK_END


# ── Step 4 — Title ────────────────────────────────────────────────────────────

async def enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title   = update.message.text.strip()
    lang    = _lang(context)
    chat_id = update.effective_chat.id

    if not title:
        await update.message.reply_text(get_text(lang, "title_empty"))
        return STATE_ENTER_TITLE
    if len(title) > 80:
        await update.message.reply_text(get_text(lang, "title_too_long", length=len(title)))
        return STATE_ENTER_TITLE

    context.user_data["title"] = title
    chosen_date = context.user_data["date"]
    start_time  = context.user_data["start_time"]
    end_time    = context.user_data["end_time"]
    dur_str     = context.user_data.get("dur_str", "")
    u           = update.effective_user
    user_display = _display_name(u)

    preview = (
        f"✅ {get_text(lang, 'btn_confirm').replace('✅','').strip()}:\n\n"
        f"📋 {title}\n"
        f"📅 {chosen_date}\n"
        f"🕐 {start_time} – {end_time}  ({dur_str})\n"
        f"👤 {user_display}"
    )

    title_msg_id = context.user_data.get("title_prompt_msg_id")
    if title_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=title_msg_id,
                text=preview, reply_markup=_kb_confirm(lang),
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id, text=preview, reply_markup=_kb_confirm(lang),
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id, text=preview, reply_markup=_kb_confirm(lang),
        )

    try:
        await update.message.delete()
    except Exception:
        pass

    return STATE_CONFIRM


async def back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    start_time  = context.user_data["start_time"]
    dur_str     = context.user_data.get("dur_str", "")

    back_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_end")
    ]])
    msg = await query.edit_message_text(
        get_text(lang, "enter_title_again",
                 date=chosen_date, hour=start_time, duration=dur_str),
        reply_markup=back_kb,
    )
    context.user_data["title_prompt_msg_id"] = msg.message_id
    return STATE_ENTER_TITLE


# ── Step 5 — Confirm ──────────────────────────────────────────────────────────

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang     = _lang(context)
    user     = update.effective_user
    username = user.username or user.first_name or str(user.id)
    import database as _db
    _db.upsert_user(user.id, username, lang)
    ud = context.user_data

    start_time = ud["start_time"]
    end_time   = ud["end_time"]
    start_min  = ud["start_min"]
    end_min    = ud["end_min"]
    dur_min    = end_min - start_min

    # Final conflict check
    conflict = _has_conflict_range(ud["date"], start_min, end_min)
    if conflict:
        await query.edit_message_text(
            get_text(lang, "booking_conflict",
                     start=conflict.start_time, end=conflict.end_time,
                     title=conflict.title, user=conflict.username),
            reply_markup=_kb_menu(lang),
        )
        lang = context.user_data.get("lang", "en")
        context.user_data.clear()
        context.user_data["lang"] = lang
        return ConversationHandler.END

    # duration in hours for DB (round up to at least 1)
    duration_h = max(1, round(dur_min / 60))

    new_booking, db_conflict = create_booking(
        user_id=user.id, username=username,
        title=ud["title"], date=ud["date"],
        start_time=start_time,
        duration=duration_h,
    )

    if db_conflict:
        await query.edit_message_text(
            get_text(lang, "booking_conflict",
                     start=db_conflict.start_time, end=db_conflict.end_time,
                     title=db_conflict.title, user=db_conflict.username),
            reply_markup=_kb_menu(lang),
        )
        lang = context.user_data.get("lang", "en")
        context.user_data.clear()
        context.user_data["lang"] = lang
        return ConversationHandler.END

    await query.edit_message_text(
        get_text(lang, "booking_confirmed", details=new_booking.full_text()),
        reply_markup=_kb_menu(lang),
    )

    # Log + notify
    try:
        await log_booking(context.bot, username=new_booking.username,
                          title=new_booking.title, date=new_booking.date,
                          start=new_booking.start_time, end=new_booking.end_time)
    except Exception:
        pass

    try:
        import datetime as _dt
        import database as _db2
        from telegram import InlineKeyboardButton as _IKB, InlineKeyboardMarkup as _IKM
        day_name     = _dt.date.fromisoformat(new_booking.date).strftime("%A, %b %d")
        all_user_ids = _db2.get_all_user_ids()
        for uid in all_user_ids:
            if uid == user.id:
                continue
            try:
                with _db2._connect() as conn:
                    row = conn.execute("SELECT lang FROM users WHERE user_id=?", (uid,)).fetchone()
                ul = row["lang"] if row else "en"
                msg_text = "📢 " + get_text(ul, "group_notification",
                               day=day_name,
                               start=new_booking.start_time,
                               end=new_booking.end_time,
                               title=new_booking.title,
                               user=new_booking.display_user)
                sent = await context.bot.send_message(
                    chat_id=uid, text=msg_text,
                    reply_markup=_IKM([[_IKB(get_text(ul, "btn_dismiss"), callback_data="notif_dismiss")]]),
                )
                import asyncio as _aio
                _aio.ensure_future(_auto_del_msg(context.bot, uid, sent.message_id))
                notifs = context.bot_data.setdefault("pending_notifs", {})
                notifs.setdefault(uid, []).append(sent.message_id)
                _db2.save_notification(uid, uid, sent.message_id)
            except Exception as exc:
                logger.warning("Notify user_id=%d failed: %s", uid, exc)
    except Exception:
        pass

    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


# ── Cancel / Dismiss ──────────────────────────────────────────────────────────

async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    from handlers.start import _main_menu_keyboard
    await query.edit_message_text(
        get_text(lang, "start_message"),
        reply_markup=_main_menu_keyboard(lang),
    )
    if update.effective_user:
        context.bot_data.setdefault("menu_msgs", {})[update.effective_user.id] = query.message.message_id
    return ConversationHandler.END


async def notif_dismiss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass


async def change_lang_in_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang
    import database as _db
    user = update.effective_user
    if user:
        username = user.username or user.first_name or str(user.id)
        _db.upsert_user(user.id, username, lang)
    return STATE_PICK_DATE


async def _ignore_start_in_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    try:
        await update.message.delete()
    except Exception:
        pass
    return STATE_PICK_DATE


# Quick-jump anchors: label → target hour
QUICK_JUMPS = [
    ("🌅", 7),   # Morning
    ("☀️", 12),  # Noon
    ("🌆", 17),  # Evening
    ("🌙", 21),  # Night
]


def _quick_jump_row(total_pages: int, slots: list) -> list:
    """Row of quick-jump buttons to common time periods."""
    buttons = []
    for emoji, hour in QUICK_JUMPS:
        target_min = hour * 60
        # Find which page contains this hour
        for i, slot in enumerate(slots):
            if slot >= target_min:
                page = i // PAGE_SIZE
                buttons.append(InlineKeyboardButton(emoji, callback_data=f"start_page:{page}"))
                break
    return buttons



# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_in_event_range(date_str: str, event_date: str) -> bool:
    try:
        from datetime import date as _d
        parts = event_date.replace(" ", "").split("–")
        if len(parts) == 2:
            return _d.fromisoformat(parts[0]) <= _d.fromisoformat(date_str) <= _d.fromisoformat(parts[1])
        return date_str == event_date.strip()
    except Exception:
        return False


async def _auto_del_msg(bot, chat_id: int, msg_id: int, delay: int = 300) -> None:
    import asyncio
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


async def _clear_notifications(bot, user_id: int, context) -> None:
    menu_msg_id = context.bot_data.get("menu_msgs", {}).get(user_id)
    pending = context.bot_data.get("pending_notifs", {})
    for msg_id in pending.pop(user_id, []):
        if msg_id == menu_msg_id:
            continue
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception:
            pass
    try:
        from scheduler.reminders import PENDING_NOTIFS
        for msg_id in PENDING_NOTIFS.pop(user_id, []):
            if msg_id == menu_msg_id:
                continue
            try:
                await bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                pass
    except Exception:
        pass


# ── Registration ──────────────────────────────────────────────────────────────

def register(application: Application) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_entry, pattern="^book$")],
        states={
            STATE_PICK_DATE: [
                CallbackQueryHandler(pick_month,     pattern=r"^cal_month:\d+:\d+$"),
                CallbackQueryHandler(pick_date,      pattern=r"^date:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(back_to_month,  pattern="^back_to_month$"),
                CallbackQueryHandler(cal_noop,       pattern="^cal_noop$"),
                CallbackQueryHandler(cal_past,       pattern="^cal_past$"),
                CallbackQueryHandler(book_cancel,    pattern="^book_cancel$"),
                CallbackQueryHandler(change_lang_in_flow, pattern=r"^lang:(en|ru|hy)$"),
            ],
            STATE_PICK_START: [
                CallbackQueryHandler(pick_hour_start, pattern=r"^hour:\d+$"),
                CallbackQueryHandler(pick_start,      pattern=r"^start:\d+$"),
                CallbackQueryHandler(back_to_hours,   pattern="^back_to_hours$"),
                CallbackQueryHandler(slot_busy,       pattern="^slot_busy$"),
                CallbackQueryHandler(back_to_date,    pattern="^back_to_date$"),
                CallbackQueryHandler(book_cancel,     pattern="^book_cancel$"),
                CallbackQueryHandler(change_lang_in_flow, pattern=r"^lang:(en|ru|hy)$"),
            ],
            STATE_PICK_END: [
                CallbackQueryHandler(pick_hour_end,       pattern=r"^end_hour:\d+$"),
                CallbackQueryHandler(pick_end,            pattern=r"^end:\d+$"),
                CallbackQueryHandler(back_to_end_hours,   pattern="^back_to_end_hours$"),
                CallbackQueryHandler(slot_busy,           pattern="^slot_busy$"),
                CallbackQueryHandler(back_to_start,       pattern="^back_to_start$"),
                CallbackQueryHandler(book_cancel,         pattern="^book_cancel$"),
                CallbackQueryHandler(change_lang_in_flow, pattern=r"^lang:(en|ru|hy)$"),
            ],
            STATE_ENTER_TITLE: [
                CallbackQueryHandler(change_lang_in_flow, pattern=r"^lang:(en|ru|hy)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_title),
                CommandHandler("start", _ignore_start_in_flow),
                CallbackQueryHandler(back_to_end,    pattern="^back_to_end$"),
                CallbackQueryHandler(book_cancel,    pattern="^book_cancel$"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(confirm_booking, pattern="^confirm_yes$"),
                CallbackQueryHandler(back_to_title,  pattern="^back_to_title$"),
                CallbackQueryHandler(book_cancel,    pattern="^book_cancel$"),
                CallbackQueryHandler(change_lang_in_flow, pattern=r"^lang:(en|ru|hy)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", book_cancel),
            CallbackQueryHandler(book_cancel, pattern="^menu$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
    application.add_handler(conv)
    application.add_handler(CallbackQueryHandler(notif_dismiss, pattern="^notif_dismiss$"))