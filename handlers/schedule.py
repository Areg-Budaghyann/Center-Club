"""
handlers/schedule.py
--------------------
View schedule (weekly/monthly) and Free Time flow.

Free Time flow (rebuilt to match booking flow):
    [Free Time] -> Month picker -> Day grid -> Show free + booked slots
"""

import calendar
from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from translations import get_text, MONTH_SHORT, DEFAULT_LANG, WEEKDAY_HEADERS
from services.schedule_service import (
    build_weekly_schedule,
    build_monthly_schedule,
    get_free_slots,
    format_free_slots,
)

def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)

def _club(context) -> str:
    return context.user_data.get("club_id", "")


def _back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")
    ]])


# ===========================================================================
# Schedule (weekly / monthly)
# ===========================================================================

async def schedule_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "btn_this_week"),  callback_data="sched:week:0"),
            InlineKeyboardButton(get_text(lang, "btn_next_week"),  callback_data="sched:week:1"),
        ],
        [
            InlineKeyboardButton(get_text(lang, "btn_this_month"), callback_data="sched:month:0"),
            InlineKeyboardButton(get_text(lang, "btn_next_month"), callback_data="sched:month:1"),
        ],
        [InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")],
    ])
    await query.edit_message_text(
        get_text(lang, "schedule_title"),
        reply_markup=keyboard,
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    _, period, offset_str = query.data.split(":")
    offset = int(offset_str)
    today  = date.today()

    club_id = _club(context)
    if period == "week":
        ref  = today + timedelta(weeks=offset)
        text = build_weekly_schedule(ref, lang, club_id=club_id)
    else:
        y, m = today.year, today.month + offset
        if m > 12:
            m -= 12
            y += 1
        text = build_monthly_schedule(y, m, lang, club_id=club_id)

    await query.edit_message_text(
        text,
        reply_markup=_back(lang),
    )


# ===========================================================================
# Free Time — rebuilt to match booking flow
# Month -> Day -> Show slots
# ===========================================================================

def _kb_freetime_month(lang: str) -> InlineKeyboardMarkup:
    """Same month grid as booking — current month through December."""
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"ft_month:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def _kb_freetime_day(year: int, month: int, lang: str, club_id: str = "") -> tuple[InlineKeyboardMarkup, str]:
    """Calendar day grid for free time — same look as booking."""
    today      = date.today()
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"

    headers = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    header_row = [InlineKeyboardButton(h, callback_data="ft_noop") for h in headers]
    rows = [header_row]

    # Get event dates for this month
    import database as _fdb
    ft_events = _fdb.get_special_events_for_month(year, month, club_id=club_id)
    ft_event_dates = set()
    for ev in ft_events:
        parts = ev["event_date"].replace(" ", "").split("–")
        if len(parts) == 2:
            try:
                from datetime import date as _d2
                s = _d2.fromisoformat(parts[0])
                e = _d2.fromisoformat(parts[1])
                cur = s
                while cur <= e:
                    ft_event_dates.add(cur.isoformat())
                    cur = _d2.fromordinal(cur.toordinal() + 1)
            except Exception:
                pass
        else:
            ft_event_dates.add(ev["event_date"].strip())

    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ft_noop"))
            else:
                d = date(year, month, day_num)
                has_ev = d.isoformat() in ft_event_dates
                if d < today:
                    row.append(InlineKeyboardButton(str(day_num), callback_data="ft_past"))
                elif d == today:
                    label = f"[{day_num}]🎉" if has_ev else f"[{day_num}]"
                    row.append(InlineKeyboardButton(label, callback_data=f"ft_day:{d.isoformat()}"))
                else:
                    label = f"{day_num}🎉" if has_ev else str(day_num)
                    row.append(InlineKeyboardButton(label, callback_data=f"ft_day:{d.isoformat()}"))
        rows.append(row)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="ft_back_month")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")])
    return InlineKeyboardMarkup(rows), month_label


async def freetime_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry: show month picker."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    await query.edit_message_text(
        get_text(lang, "free_time_title"),
        reply_markup=_kb_freetime_month(lang),
    )


async def freetime_pick_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Month chosen — show day grid."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    _, year_str, month_str = query.data.split(":")
    year, month = int(year_str), int(month_str)
    context.user_data["ft_year"]  = year
    context.user_data["ft_month"] = month

    keyboard, month_label = _kb_freetime_day(year, month, lang, club_id=_club(context))
    await query.edit_message_text(
        f"📅 {month_label}",
        reply_markup=keyboard,
    )


async def freetime_back_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Back to month picker."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(
        get_text(lang, "free_time_title"),
        reply_markup=_kb_freetime_month(lang),
    )


async def freetime_pick_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Day chosen — show free + booked slots."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    target_date = date.fromisoformat(query.data.split(":")[1])
    club_id = _club(context)

    # Get free slots
    free_slots = get_free_slots(target_date, club_id=club_id)

    # Get booked slots
    import database as _db
    bookings = _db.get_bookings_for_date(target_date.isoformat(), club_id=club_id)

    month_name = MONTH_SHORT[lang][target_date.month - 1]
    day_str = f"{target_date.day} {month_name}"
    lines   = [f"📅 {day_str}\n"]

    # Free slots section — translated labels
    free_label    = get_text(lang, "free_label")
    booked_label  = get_text(lang, "booked_label")
    no_free_label = get_text(lang, "no_free_label")

    if free_slots:
        lines.append(free_label)
        for s, e in free_slots:
            lines.append(f"  {s} – {e}")
    else:
        lines.append(no_free_label)

    # Booked slots section
    if bookings:
        lines.append("\n" + booked_label)
        for b in bookings:
            lines.append(f"  {b.start_time} – {b.end_time} | {b.title} (@{b.username})")
    else:
        lines.append("\n" + get_text(lang, "no_bookings_day"))

    # Special events section
    import database as _db2
    from services.schedule_service import _date_in_event_range_str
    day_events = [e for e in _db2.get_all_special_events(club_id=club_id)
                  if _date_in_event_range_str(target_date.isoformat(), e["event_date"])]
    if day_events:
        lines.append("\n🎉 Special events:")
        for ev in day_events:
            lines.append(f"  📌 {ev['title']}")
            if ev.get("location"):
                lines.append(f"  📍 {ev['location']}")

    # Back button to day grid
    year  = context.user_data.get("ft_year")
    month = context.user_data.get("ft_month")
    if year and month:
        keyboard, _ = _kb_freetime_day(year, month, lang, club_id=club_id)
    else:
        keyboard = _kb_freetime_month(lang)

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(lang, "btn_back"), callback_data=f"ft_back_month")],
            [InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")],
        ]),
    )


async def ft_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


async def ft_past(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(context)
    await update.callback_query.answer(get_text(lang, "past_day_alert"), show_alert=True)


# ===========================================================================
# Registration
# ===========================================================================

def register(application) -> None:
    # Schedule
    application.add_handler(CallbackQueryHandler(schedule_entry,    pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(schedule_callback, pattern=r"^sched:"))

    # Free Time
    application.add_handler(CallbackQueryHandler(freetime_entry,        pattern="^freetime$"))
    application.add_handler(CallbackQueryHandler(freetime_pick_month,   pattern=r"^ft_month:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(freetime_back_month,   pattern="^ft_back_month$"))
    application.add_handler(CallbackQueryHandler(freetime_pick_day,     pattern=r"^ft_day:\d{4}-\d{2}-\d{2}$"))
    application.add_handler(CallbackQueryHandler(ft_noop,               pattern="^ft_noop$"))
    application.add_handler(CallbackQueryHandler(ft_past,               pattern="^ft_past$"))