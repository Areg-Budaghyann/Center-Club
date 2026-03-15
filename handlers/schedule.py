"""
handlers/schedule.py
--------------------
View schedule (weekly / monthly) and free time handlers.
"""

from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from translations import get_text, DEFAULT_LANG
from services.schedule_service import (
    build_weekly_schedule,
    build_monthly_schedule,
    format_free_slots,
)

def _back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]])


# ── Schedule entry ────────────────────────────────────────────────────────────

async def schedule_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "btn_this_week"),  callback_data="sched:week:0"),
            InlineKeyboardButton(get_text(lang, "btn_next_week"),     callback_data="sched:week:1"),
        ],
        [
            InlineKeyboardButton(get_text(lang, "btn_this_month"), callback_data="sched:month:0"),
            InlineKeyboardButton(get_text(lang, "btn_next_month"),    callback_data="sched:month:1"),
        ],
        [InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")],
    ])
    await query.edit_message_text(
        get_text(lang, "schedule_title"),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)

    # pattern: sched:week:0 / sched:month:1
    _, period, offset_str = query.data.split(":")
    offset = int(offset_str)

    today = date.today()

    if period == "week":
        ref = today + timedelta(weeks=offset)
        text = build_weekly_schedule(ref)
    else:  # month
        import calendar
        # Move to next month if offset=1
        y, m = today.year, today.month
        m += offset
        if m > 12:
            m -= 12
            y += 1
        text = build_monthly_schedule(y, m)

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=_back(lang),
    )


# ── Free time ─────────────────────────────────────────────────────────────────

async def freetime_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    today = date.today()
    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        label = d.strftime("%a %d %b") if i > 0 else f"Today ({d.strftime('%d %b')})"
        row.append(InlineKeyboardButton(label, callback_data=f"free:{d.isoformat()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")])
    await query.edit_message_text(
        get_text(lang, "free_time_title"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def freetime_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    target_date = date.fromisoformat(query.data.split(":")[1])
    text = format_free_slots(target_date)
    # Append "no bookings" note when the whole day is free
    import database as _db
    if not _db.get_bookings_for_date(target_date.isoformat()):
        text += "\n\n📭 No bookings for this day."
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=_back(lang),
    )


# ── Registration ──────────────────────────────────────────────────────────────

def register(application) -> None:
    application.add_handler(CallbackQueryHandler(schedule_entry,    pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(schedule_callback, pattern=r"^sched:"))
    application.add_handler(CallbackQueryHandler(freetime_entry,    pattern="^freetime$"))
    application.add_handler(CallbackQueryHandler(freetime_callback, pattern=r"^free:"))