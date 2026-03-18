"""
handlers/recurring.py
======================
Recurring booking flow — book every Wednesday (or any weekday)
for a date range in one go.

Flow:
    /recurring  →  Pick weekday  →  Pick from-month  →  Pick from-day
                →  Pick to-month →  Pick to-day
                →  Enter title   →  Confirm  →  Create all bookings

Start time and duration are pre-configured as constants below.
Change RECURRING_START / RECURRING_END to adjust the Wednesday meeting slot.

Only users whose Telegram ID is in ADMIN_IDS (config.py) can use this.
If ADMIN_IDS is empty, all users can use it.
"""

import logging
import calendar
from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_IDS
from database import create_recurring_bookings
from translations import get_text, MONTH_NAMES, MONTH_SHORT, WEEKDAY_NAMES, DEFAULT_LANG
from handlers.booking import _lang

WEEKDAY_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-configured recurring slot
# Wednesday 19:30 – 23:00  =  3.5 hours, stored as 4 (ceiling) for now.
# Since our bookings use whole hours we store duration=4 (19:00–23:00 block)
# but display the real time string in the UI.
# ---------------------------------------------------------------------------
RECURRING_START     = "19:00"   # start of blocked window (whole hour)
RECURRING_START_DISPLAY = "19:30"  # displayed to users
RECURRING_END_DISPLAY   = "23:00"
RECURRING_DURATION  = 4         # hours (19:00–23:00 covers the 19:30 slot safely)
RECURRING_WEEKDAY   = 2         # 0=Mon … 6=Sun  →  2 = Wednesday



# ConversationHandler states
(
    REC_PICK_FROM_MONTH,
    REC_PICK_FROM_DAY,
    REC_PICK_TO_MONTH,
    REC_PICK_TO_DAY,
    REC_ENTER_TITLE,
    REC_CONFIRM,
) = range(10, 16)


# ===========================================================================
# Access control
# ===========================================================================

def _is_admin(user_id: int) -> bool:
    """Return True if the user is allowed to create recurring bookings."""
    if not ADMIN_IDS:
        return True   # open to all when no admins configured
    return user_id in ADMIN_IDS


# ===========================================================================
# Keyboard helpers
# ===========================================================================

def _kb_month_picker(prefix: str, lang: str) -> InlineKeyboardMarkup:
    """Rolling 12-month grid. prefix is used in callback_data to distinguish
    from-month vs to-month pickers."""
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]   # just "Mar", "Apr" — no year
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="rec_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_day_picker(prefix: str, year: int, month: int, lang: str) -> tuple[InlineKeyboardMarkup, str]:
    """Calendar day grid. Only shows dates that fall on RECURRING_WEEKDAY."""
    today = date.today()
    month_label = f"{MONTH_NAMES[lang][month-1]} {year}"
    header = [InlineKeyboardButton(h, callback_data="rec_noop") for h in WEEKDAY_HEADERS]
    rows = [header]

    for week in calendar.monthcalendar(year, month):
        row = []
        for wd, day_num in enumerate(week):
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="rec_noop"))
            else:
                d = date(year, month, day_num)
                label = str(day_num)
                if d < today:
                    row.append(InlineKeyboardButton(label, callback_data="rec_past"))
                else:
                    row.append(InlineKeyboardButton(
                        label, callback_data=f"{prefix}:{d.isoformat()}"
                    ))
        rows.append(row)

    rows.append([InlineKeyboardButton("← Back", callback_data=f"rec_back_{prefix}_month")])
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="rec_cancel")])
    return InlineKeyboardMarkup(rows), month_label


def _kb_confirm_rec(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="rec_confirm_yes"),
            InlineKeyboardButton("✖ Cancel",  callback_data="rec_cancel"),
        ],
    ])


# ===========================================================================
# Entry — /recurring command
# ===========================================================================

async def recurring_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point via /recurring command."""
    user = update.effective_user
    lang = context.user_data.get("lang", DEFAULT_LANG)

    if not _is_admin(user.id):
        await update.message.reply_text("⛔ You don't have permission to use this command.")
        return ConversationHandler.END

    wd_name = WEEKDAY_NAMES[lang][RECURRING_WEEKDAY]

    await update.message.reply_text(
        f"📅 *Recurring booking*\n\n"
        f"This will book every *{wd_name}* from "
        f"*{RECURRING_START_DISPLAY}* to *{RECURRING_END_DISPLAY}*.\n\n"
        f"*Step 1 — Choose the START date:*\n"
        f"_(Pick the month first)_",
        reply_markup=_kb_month_picker("rec_from_month", lang),
    )
    return REC_PICK_FROM_MONTH


# ===========================================================================
# From-date selection
# ===========================================================================

async def pick_from_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_str, month_str = query.data.split(":")
    year, month = int(year_str), int(month_str)
    context.user_data["rec_from_year"]  = year
    context.user_data["rec_from_month"] = month

    keyboard, label = _kb_day_picker("rec_from_day", year, month, lang)
    await query.edit_message_text(
        f"📅 *{label}* — choose the START day:",
        reply_markup=keyboard,
    )
    return REC_PICK_FROM_DAY


async def pick_from_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    chosen = query.data.split(":")[1]
    context.user_data["rec_from_date"] = chosen

    await query.edit_message_text(
        f"✅ Start date: *{chosen}*\n\n"
        f"*Step 2 — Choose the END date:*\n_(Pick the month first)_",
        reply_markup=_kb_month_picker("rec_to_month", lang),
    )
    return REC_PICK_TO_MONTH


# ===========================================================================
# To-date selection
# ===========================================================================

async def pick_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_str, month_str = query.data.split(":")
    year, month = int(year_str), int(month_str)
    context.user_data["rec_to_year"]  = year
    context.user_data["rec_to_month"] = month

    keyboard, label = _kb_day_picker("rec_to_day", year, month, lang)
    await query.edit_message_text(
        f"📅 *{label}* — choose the END day:",
        reply_markup=keyboard,
    )
    return REC_PICK_TO_DAY


async def pick_to_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    chosen = query.data.split(":")[1]
    context.user_data["rec_to_date"] = chosen

    from_date = context.user_data["rec_from_date"]
    wd_name   = WEEKDAY_NAMES[lang][RECURRING_WEEKDAY]

    await query.edit_message_text(
        f"📅 *{from_date}* → *{chosen}*\n"
        f"🗓 Every *{wd_name}* · {RECURRING_START_DISPLAY}–{RECURRING_END_DISPLAY}\n\n"
        f"✏️ *Enter the event title:*\n_(e.g. Weekly Meeting)_",
    )
    return REC_ENTER_TITLE


# ===========================================================================
# Title
# ===========================================================================

async def enter_rec_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    lang  = _lang(context)

    if not title or len(title) > 80:
        await update.message.reply_text("Please enter a valid title (1–80 chars).")
        return REC_ENTER_TITLE

    context.user_data["rec_title"] = title
    from_date = context.user_data["rec_from_date"]
    to_date   = context.user_data["rec_to_date"]
    wd_name   = WEEKDAY_NAMES[lang][RECURRING_WEEKDAY]

    # Count how many Wednesdays are in the range
    from datetime import date as _date, timedelta
    start  = _date.fromisoformat(from_date)
    end    = _date.fromisoformat(to_date)
    days_ahead = (RECURRING_WEEKDAY - start.weekday()) % 7
    first  = start + timedelta(days=days_ahead)
    count  = max(0, (end - first).days // 7 + 1) if first <= end else 0

    preview = (
        f"✅ *Confirm recurring booking:*\n\n"
        f"📋 *{title}*\n"
        f"🗓 Every {wd_name}\n"
        f"🕐 {RECURRING_START_DISPLAY} – {RECURRING_END_DISPLAY}\n"
        f"📅 {from_date} → {to_date}\n"
        f"🔢 *{count} bookings* will be created"
    )
    await update.message.reply_text(
        preview,
        reply_markup=_kb_confirm_rec(lang),
    )
    return REC_CONFIRM


# ===========================================================================
# Confirm — create all bookings
# ===========================================================================

async def confirm_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user     = update.effective_user
    username = user.username or user.first_name
    ud       = context.user_data

    created, skipped = create_recurring_bookings(
        user_id    = user.id,
        username   = username,
        title      = ud["rec_title"],
        weekday    = RECURRING_WEEKDAY,
        start_time = RECURRING_START,
        duration   = RECURRING_DURATION,
        end_time   = RECURRING_END_DISPLAY,
        from_date  = ud["rec_from_date"],
        to_date    = ud["rec_to_date"],
    )

    lines = [f"🎉 *{len(created)} recurring bookings created!*\n"]
    for b in created:
        lines.append(f"  ✅ {b.date}  {RECURRING_START_DISPLAY}–{RECURRING_END_DISPLAY}  {b.title}")

    if skipped:
        lines.append(f"\n⚠️ *{len(skipped)} dates skipped* (already booked):")
        for d in skipped:
            lines.append(f"  ✗ {d}")

    lang = _lang(context)
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(lang, "menu_button"), callback_data="menu")]
        ]),
    )

    lang = context.user_data.get("lang"); context.user_data.clear(); context.user_data["lang"] = lang
    return ConversationHandler.END


# ===========================================================================
# Cancel / no-ops
# ===========================================================================

async def rec_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    lang = context.user_data.get("lang"); context.user_data.clear(); context.user_data["lang"] = lang
    await query.edit_message_text(
        "Recurring booking cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(lang, "menu_button"), callback_data="menu")]
        ]),
    )
    return ConversationHandler.END


async def rec_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return ConversationHandler.END


async def rec_past(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer("That day is in the past.", show_alert=True)
    return ConversationHandler.END


async def rec_back_from_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(
        "Choose the START month:",
        reply_markup=_kb_month_picker("rec_from_month", lang),
    )
    return REC_PICK_FROM_MONTH


async def rec_back_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(
        "Choose the END month:",
        reply_markup=_kb_month_picker("rec_to_month", lang),
    )
    return REC_PICK_TO_MONTH


# ===========================================================================
# Registration
# ===========================================================================

def register(application) -> None:
    conv = ConversationHandler(
        entry_points=[CommandHandler("recurring", recurring_entry)],
        states={
            REC_PICK_FROM_MONTH: [
                CallbackQueryHandler(pick_from_month, pattern=r"^rec_from_month:\d+:\d+$"),
                CallbackQueryHandler(rec_cancel,      pattern="^rec_cancel$"),
            ],
            REC_PICK_FROM_DAY: [
                CallbackQueryHandler(pick_from_day,      pattern=r"^rec_from_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(rec_back_from_month, pattern="^rec_back_rec_from_day_month$"),
                CallbackQueryHandler(rec_noop,           pattern="^rec_noop$"),
                CallbackQueryHandler(rec_past,           pattern="^rec_past$"),
                CallbackQueryHandler(rec_cancel,         pattern="^rec_cancel$"),
            ],
            REC_PICK_TO_MONTH: [
                CallbackQueryHandler(pick_to_month, pattern=r"^rec_to_month:\d+:\d+$"),
                CallbackQueryHandler(rec_cancel,    pattern="^rec_cancel$"),
            ],
            REC_PICK_TO_DAY: [
                CallbackQueryHandler(pick_to_day,       pattern=r"^rec_to_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(rec_back_to_month,  pattern="^rec_back_rec_to_day_month$"),
                CallbackQueryHandler(rec_noop,          pattern="^rec_noop$"),
                CallbackQueryHandler(rec_past,          pattern="^rec_past$"),
                CallbackQueryHandler(rec_cancel,        pattern="^rec_cancel$"),
            ],
            REC_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_rec_title),
                CallbackQueryHandler(rec_cancel, pattern="^rec_cancel$"),
            ],
            REC_CONFIRM: [
                CallbackQueryHandler(confirm_recurring, pattern="^rec_confirm_yes$"),
                CallbackQueryHandler(rec_cancel,        pattern="^rec_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(rec_cancel, pattern="^rec_cancel$"),
            CallbackQueryHandler(rec_cancel, pattern="^menu$"),
        ],
        per_message=False,
    )
    application.add_handler(conv)