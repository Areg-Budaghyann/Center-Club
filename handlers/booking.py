"""
handlers/booking.py
====================
Multi-step booking flow. Single-interface: always edits the same message.
Auto-deletes user text input after processing.

Flow: Month -> Day -> Hour -> Duration -> Title -> Confirm

RUSSIAN BUG FIX: month labels in day keyboard now use plain MONTH_SHORT
instead of full MONTH_NAMES wrapped in *bold* Markdown — Cyrillic month
names like "Июнь" inside *bold* were causing Telegram BadRequest errors.
"""

import calendar
import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters,
)

from translations import get_text, MONTH_NAMES, MONTH_SHORT, DEFAULT_LANG
from config import (
    GROUP_CHAT_ID, MAX_DURATION_HOURS, MIN_DURATION_HOURS,
    OFFICE_CLOSE, OFFICE_OPEN,
    STATE_CONFIRM, STATE_ENTER_TITLE, STATE_PICK_DATE,
    STATE_PICK_DURATION, STATE_PICK_HOUR,
)
from services.booking_service import create_booking
from services.schedule_service import get_free_slots

logger = logging.getLogger(__name__)

WEEKDAY_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _esc(text: str) -> str:
    """Escape Markdown special chars in user-provided strings."""
    for ch in ["_", "*", "`", "["]:
        text = text.replace(ch, "\\" + ch)
    return text


# ===========================================================================
# Conflict check
# ===========================================================================

def _has_conflict(date_str, start_hour, duration, exclude_id=None):
    import database
    req_start = start_hour
    req_end   = start_hour + duration
    for b in database.get_bookings_for_date(date_str):
        if exclude_id and b.id == exclude_id:
            continue
        ex_start = int(b.start_time.split(":")[0])
        ex_end   = int(b.end_time.split(":")[0])
        if req_start < ex_end and req_end > ex_start:
            return b
    return None


# ===========================================================================
# Keyboard builders
# ===========================================================================

def _kb_month(lang: str) -> InlineKeyboardMarkup:
    """Show months from current month through December — no year suffix."""
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
    """Full calendar grid. Uses MONTH_SHORT (no Markdown) to avoid Russian parser crash."""
    today      = date.today()
    # FIX: use plain MONTH_SHORT label — not *bold* MONTH_NAMES
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"

    header_row = [InlineKeyboardButton(h, callback_data="cal_noop") for h in WEEKDAY_HEADERS]
    rows = [header_row]

    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            else:
                d = date(year, month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(str(day_num), callback_data="cal_past"))
                elif d == today:
                    row.append(InlineKeyboardButton(f"[{day_num}]", callback_data=f"date:{d.isoformat()}"))
                else:
                    row.append(InlineKeyboardButton(str(day_num), callback_data=f"date:{d.isoformat()}"))
        rows.append(row)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_month")])
    rows.append([InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="book_cancel")])
    return InlineKeyboardMarkup(rows), month_label


def _kb_hour(chosen_date: str, lang: str) -> InlineKeyboardMarkup:
    """Hour grid 00:00-23:00 (24h). Booked hours show lock icon + booking id."""
    import database

    hour_to_booking = {}
    for b in database.get_bookings_for_date(chosen_date):
        for h in range(int(b.start_time.split(":")[0]), int(b.end_time.split(":")[0])):
            hour_to_booking[h] = b

    rows, row = [], []
    for h in range(OFFICE_OPEN, OFFICE_CLOSE):
        if h not in hour_to_booking:
            row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"hour:{h}"))
        else:
            booking_id = hour_to_booking[h].id
            row.append(InlineKeyboardButton(f"🔒 {h:02d}", callback_data=f"hour_busy:{booking_id}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_date")])
    return InlineKeyboardMarkup(rows)


def _kb_duration(chosen_date: str, start_hour: int, lang: str) -> InlineKeyboardMarkup:
    """Duration buttons 1-12h. Only shows options that fit without overlap."""
    import datetime as _dt

    free_slots = get_free_slots(_dt.date.fromisoformat(chosen_date))
    max_avail  = OFFICE_CLOSE - start_hour

    for s, e in free_slots:
        sh, eh = int(s.split(":")[0]), int(e.split(":")[0])
        if sh <= start_hour < eh:
            max_avail = min(max_avail, eh - start_hour)
            break

    rows, row = [], []
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

    rows.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_to_hour")])
    return InlineKeyboardMarkup(rows)


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


# ===========================================================================
# Step 1 — Month picker
# ===========================================================================

async def book_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — preserves lang, clears other state."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    await query.edit_message_text(
        get_text(lang, "choose_month"),
        parse_mode="Markdown",
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
    # FIX: month_label uses plain text (no *bold*) so Russian names don't crash parser
    await query.edit_message_text(
        f"📅 {month_label} — {get_text(lang, 'choose_day', month='').split('—')[-1].strip()}",
        reply_markup=keyboard,
    )
    return STATE_PICK_DATE


async def back_to_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(
        get_text(lang, "choose_month"),
        parse_mode="Markdown",
        reply_markup=_kb_month(lang),
    )
    return STATE_PICK_DATE


async def pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.split(":")[1]
    lang = _lang(context)
    context.user_data["date"] = chosen_date

    await query.edit_message_text(
        get_text(lang, "choose_time", date=chosen_date),
        parse_mode="Markdown",
        reply_markup=_kb_hour(chosen_date, lang),
    )
    return STATE_PICK_HOUR


async def back_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data.get("cal_year")
    month = context.user_data.get("cal_month")

    if year and month:
        keyboard, month_label = _kb_day(year, month, lang)
        await query.edit_message_text(
            f"📅 {month_label}",
            reply_markup=keyboard,
        )
    else:
        await query.edit_message_text(
            get_text(lang, "choose_month"),
            parse_mode="Markdown",
            reply_markup=_kb_month(lang),
        )
    return STATE_PICK_DATE


async def cal_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return STATE_PICK_DATE


async def cal_past(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    await update.callback_query.answer(get_text(lang, "past_day_alert"), show_alert=True)
    return STATE_PICK_DATE


# ===========================================================================
# Step 2 — Hour
# ===========================================================================

async def pick_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang  = _lang(context)

    if query.data.startswith("hour_busy"):
        import database
        try:
            b = database.get_booking_by_id(int(query.data.split(":")[1]))
            alert = (
                get_text(lang, "slot_taken_detail",
                         title=_esc(b.title),
                         start=b.start_time,
                         end=b.end_time,
                         user=_esc(b.username))
                if b else get_text(lang, "slot_taken_alert")
            )
        except Exception:
            alert = get_text(lang, "slot_taken_alert")
        await query.answer(alert, show_alert=True)
        return STATE_PICK_HOUR

    await query.answer()
    hour = int(query.data.split(":")[1])
    chosen_date = context.user_data["date"]
    context.user_data["start_hour"] = hour

    await query.edit_message_text(
        get_text(lang, "choose_duration", date=chosen_date, hour=f"{hour:02d}"),
        parse_mode="Markdown",
        reply_markup=_kb_duration(chosen_date, hour, lang),
    )
    return STATE_PICK_DURATION


async def back_to_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    chosen_date = context.user_data["date"]

    await query.edit_message_text(
        get_text(lang, "choose_time", date=chosen_date),
        parse_mode="Markdown",
        reply_markup=_kb_hour(chosen_date, lang),
    )
    return STATE_PICK_HOUR


# ===========================================================================
# Step 3 — Duration
# ===========================================================================

async def pick_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    duration    = int(query.data.split(":")[1])
    lang        = _lang(context)
    chosen_date = context.user_data["date"]
    start_hour  = context.user_data["start_hour"]
    context.user_data["duration"] = duration

    # Plain text — no Markdown parse_mode to avoid any BadRequest
    await query.edit_message_text(
        get_text(lang, "enter_title",
                 date=chosen_date,
                 hour=f"{start_hour:02d}",
                 duration=duration),
    )
    return STATE_ENTER_TITLE


async def back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    )
    return STATE_ENTER_TITLE


# ===========================================================================
# Step 4 — Title (auto-deletes user message for clean UI)
# ===========================================================================

async def enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the user's typed booking title.

    BUG FIX:
    --------
    Previous order was:
        1. delete message
        2. reply to deleted message  <-- this fails silently on some API versions

    Correct order is:
        1. Read title from message FIRST (before any deletion)
        2. Validate title
        3. Save to user_data
        4. Send confirmation via context.bot.send_message (NOT reply_text)
           because reply_text uses the message object which may be gone
        5. Delete the user message LAST (fire-and-forget, never blocks flow)
    """
    # Step 1 — Read everything we need BEFORE touching the message
    title   = update.message.text.strip()
    lang    = _lang(context)
    chat_id = update.effective_chat.id

    # Step 2 — Validate BEFORE deleting so we can reply if invalid
    if not title:
        # Don't delete — user needs to see their message to correct it
        await update.message.reply_text(get_text(lang, "title_empty"))
        return STATE_ENTER_TITLE

    if len(title) > 80:
        await update.message.reply_text(
            get_text(lang, "title_too_long", length=len(title))
        )
        return STATE_ENTER_TITLE

    # Step 3 — Title is valid, save to conversation state
    context.user_data["title"] = title
    chosen_date  = context.user_data["date"]
    start_hour   = context.user_data["start_hour"]
    duration     = context.user_data["duration"]
    end_hour     = start_hour + duration
    display_name = update.effective_user.username or update.effective_user.first_name

    # Step 4 — Send confirmation using chat_id directly (not reply_text)
    # This works even after the user message is deleted
    await context.bot.send_message(
        chat_id    = chat_id,
        text       = get_text(lang, "confirm_preview",
                              title=_esc(title),
                              date=chosen_date,
                              start=f"{start_hour:02d}",
                              end=f"{end_hour:02d}",
                              duration=duration,
                              user=_esc(display_name)),
        parse_mode = "Markdown",
        reply_markup = _kb_confirm(lang),
    )

    # Step 5 — Delete user message LAST, silently (never blocks flow)
    try:
        await update.message.delete()
    except Exception:
        pass  # Message already gone or no permission — doesn't matter

    return STATE_CONFIRM


# ===========================================================================
# Confirm
# ===========================================================================

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query    = update.callback_query
    await query.answer()
    lang     = _lang(context)
    user     = update.effective_user
    username = user.username or user.first_name
    ud       = context.user_data

    conflict = _has_conflict(ud["date"], ud["start_hour"], ud["duration"])
    if conflict:
        await query.edit_message_text(
            get_text(lang, "booking_conflict",
                     start=conflict.start_time,
                     end=conflict.end_time,
                     title=_esc(conflict.title),
                     user=_esc(conflict.username)),
            parse_mode="Markdown",
            reply_markup=_kb_menu(lang),
        )
        return ConversationHandler.END

    new_booking, db_conflict = create_booking(
        user_id=user.id, username=username,
        title=ud["title"], date=ud["date"],
        start_time=f"{ud['start_hour']:02d}:00",
        duration=ud["duration"],
    )

    if db_conflict:
        await query.edit_message_text(
            get_text(lang, "booking_conflict",
                     start=db_conflict.start_time,
                     end=db_conflict.end_time,
                     title=_esc(db_conflict.title),
                     user=_esc(db_conflict.username)),
            parse_mode="Markdown",
            reply_markup=_kb_menu(lang),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        get_text(lang, "booking_confirmed", details=new_booking.full_text()),
        parse_mode="Markdown",
        reply_markup=_kb_menu(lang),
    )

    # Broadcast to all users
    if True:
        import datetime as _dt
        import database as _db
        day_name = _dt.date.fromisoformat(new_booking.date).strftime("%A, %b %d")
        all_user_ids = _db.get_all_user_ids()

        for uid in all_user_ids:
            if uid == user.id:
                continue
            try:
                with _db._connect() as conn:
                    row = conn.execute("SELECT lang FROM users WHERE user_id=?", (uid,)).fetchone()
                ul = row["lang"] if row else "en"
                msg = (
                    "📢 *" + get_text(ul, "btn_book_office") + "*\n\n"
                    + get_text(ul, "group_notification",
                               day=day_name,
                               start=new_booking.start_time,
                               end=new_booking.end_time,
                               title=_esc(new_booking.title),
                               user=_esc(new_booking.username))
                )
                await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            except Exception as exc:
                logger.warning("Notify user_id=%d failed: %s", uid, exc)

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=get_text("en", "group_notification",
                                  day=day_name,
                                  start=new_booking.start_time,
                                  end=new_booking.end_time,
                                  title=_esc(new_booking.title),
                                  user=_esc(new_booking.username)),
                    parse_mode="Markdown",
                )
            except Exception as exc:
                logger.warning("Group notification failed: %s", exc)

    lang = context.user_data.get("lang")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


# ===========================================================================
# Cancel
# ===========================================================================

async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    lang_val = lang
    context.user_data.clear()
    context.user_data["lang"] = lang_val

    await query.edit_message_text(
        get_text(lang, "booking_cancelled"),
        reply_markup=_kb_menu(lang),
    )
    return ConversationHandler.END


# ===========================================================================
# Registration
# ===========================================================================

def register(application) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_entry, pattern="^book$")],
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
        fallbacks=[CallbackQueryHandler(book_cancel, pattern="^book_cancel$")],
        per_message=False,
    )
    application.add_handler(conv)
