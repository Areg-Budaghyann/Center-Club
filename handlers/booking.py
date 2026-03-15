"""
handlers/booking.py
--------------------
Multi-step booking flow using ConversationHandler.

States:
  STATE_PICK_DATE     → inline calendar (next 14 days)
  STATE_PICK_HOUR     → pick start hour
  STATE_PICK_DURATION → pick 1-6 hours
  STATE_ENTER_TITLE   → user types a title
  STATE_CONFIRM       → preview + confirm / go back
"""

import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import (
    OFFICE_OPEN,
    OFFICE_CLOSE,
    MAX_DURATION_HOURS,
    MIN_DURATION_HOURS,
    STATE_PICK_DATE,
    STATE_PICK_HOUR,
    STATE_PICK_DURATION,
    STATE_ENTER_TITLE,
    STATE_CONFIRM,
    GROUP_CHAT_ID,
)
from services.booking_service import create_booking
from services.schedule_service import get_free_slots

logger = logging.getLogger(__name__)

# ── Keyboard builders ─────────────────────────────────────────────────────────

def _date_keyboard() -> InlineKeyboardMarkup:
    """Inline calendar: today + next 13 days, 3 per row."""
    today = date.today()
    buttons, row = [], []
    for i in range(14):
        d = today + timedelta(days=i)
        label = d.strftime("%a %d %b") if i > 0 else f"Today {d.strftime('%d %b')}"
        row.append(InlineKeyboardButton(label, callback_data=f"date:{d.isoformat()}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✖ Cancel", callback_data="book_cancel")])
    return InlineKeyboardMarkup(buttons)


def _hour_keyboard(chosen_date: str) -> InlineKeyboardMarkup:
    """Show only hours that still have at least 1 free hour remaining."""
    booked_ranges = [
        (int(b.start_time.split(":")[0]), int(b.end_time.split(":")[0]))
        for b in __import__("database").get_bookings_for_date(chosen_date)
    ]

    def is_hour_available(h: int) -> bool:
        for start, end in booked_ranges:
            if start <= h < end:
                return False
        return True

    buttons, row = [], []
    for h in range(OFFICE_OPEN, OFFICE_CLOSE):
        label = f"{h:02d}:00" if is_hour_available(h) else f"✗ {h:02d}:00"
        cb = f"hour:{h}" if is_hour_available(h) else "hour_busy"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("← Back", callback_data="back_to_date")])
    return InlineKeyboardMarkup(buttons)


def _duration_keyboard(chosen_date: str, start_hour: int) -> InlineKeyboardMarkup:
    """Only show durations that fit within office hours and don't overlap bookings."""
    free_slots = get_free_slots(__import__("datetime").date.fromisoformat(chosen_date))
    # Find max available hours from start_hour
    max_avail = OFFICE_CLOSE - start_hour
    for slot_start, slot_end in free_slots:
        sh = int(slot_start.split(":")[0])
        eh = int(slot_end.split(":")[0])
        if sh <= start_hour < eh:
            max_avail = min(max_avail, eh - start_hour)
            break

    buttons = []
    row = []
    for d in range(MIN_DURATION_HOURS, MAX_DURATION_HOURS + 1):
        if d <= max_avail:
            row.append(InlineKeyboardButton(f"{d}h", callback_data=f"dur:{d}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if not any(b for b in buttons):
        buttons = [[InlineKeyboardButton("No slots available", callback_data="noop")]]
    buttons.append([InlineKeyboardButton("← Back", callback_data="back_to_hour")])
    return InlineKeyboardMarkup(buttons)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_yes"),
            InlineKeyboardButton("✖ Cancel",  callback_data="book_cancel"),
        ],
        [InlineKeyboardButton("← Change title", callback_data="back_to_title")],
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

async def book_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: called when user taps 📅 Book office."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "📅 *Step 1 of 4 — Choose a date:*",
        parse_mode="Markdown",
        reply_markup=_date_keyboard(),
    )
    return STATE_PICK_DATE


# ── Step 1: pick date ─────────────────────────────────────────────────────────

async def pick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":")[1]
    context.user_data["date"] = chosen
    await query.edit_message_text(
        f"📅 *{chosen}*\n\n🕐 *Step 2 of 4 — Choose start time:*",
        parse_mode="Markdown",
        reply_markup=_hour_keyboard(chosen),
    )
    return STATE_PICK_HOUR


async def back_to_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📅 *Step 1 of 4 — Choose a date:*",
        parse_mode="Markdown",
        reply_markup=_date_keyboard(),
    )
    return STATE_PICK_DATE


# ── Step 2: pick hour ─────────────────────────────────────────────────────────

async def pick_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "hour_busy":
        await query.answer("That hour is already taken — pick another.", show_alert=True)
        return STATE_PICK_HOUR

    hour = int(query.data.split(":")[1])
    context.user_data["start_hour"] = hour
    chosen_date = context.user_data["date"]
    await query.edit_message_text(
        f"📅 {chosen_date} | 🕐 {hour:02d}:00\n\n⏱ *Step 3 of 4 — Choose duration:*",
        parse_mode="Markdown",
        reply_markup=_duration_keyboard(chosen_date, hour),
    )
    return STATE_PICK_DURATION


async def back_to_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date = context.user_data["date"]
    await query.edit_message_text(
        f"📅 *{chosen_date}*\n\n🕐 *Step 2 of 4 — Choose start time:*",
        parse_mode="Markdown",
        reply_markup=_hour_keyboard(chosen_date),
    )
    return STATE_PICK_HOUR


# ── Step 3: pick duration ─────────────────────────────────────────────────────

async def pick_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    duration = int(query.data.split(":")[1])
    context.user_data["duration"] = duration
    chosen_date  = context.user_data["date"]
    start_hour   = context.user_data["start_hour"]
    await query.edit_message_text(
        f"📅 {chosen_date} | 🕐 {start_hour:02d}:00 | ⏱ {duration}h\n\n"
        "✏️ *Step 4 of 4 — Enter event title:*\n\n"
        "_Type the name of your event (e.g. Board Games, Team Meeting)_",
        parse_mode="Markdown",
    )
    return STATE_ENTER_TITLE


async def back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_date  = context.user_data["date"]
    start_hour   = context.user_data["start_hour"]
    duration     = context.user_data["duration"]
    await query.edit_message_text(
        f"📅 {chosen_date} | 🕐 {start_hour:02d}:00 | ⏱ {duration}h\n\n"
        "✏️ *Step 4 of 4 — Enter event title:*\n\n"
        "_Type the name of your event_",
        parse_mode="Markdown",
    )
    return STATE_ENTER_TITLE


# ── Step 4: enter title ───────────────────────────────────────────────────────

async def enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Please enter a valid title.")
        return STATE_ENTER_TITLE
    if len(title) > 80:
        await update.message.reply_text("Title too long (max 80 chars). Try again.")
        return STATE_ENTER_TITLE

    context.user_data["title"] = title
    chosen_date = context.user_data["date"]
    start_hour  = context.user_data["start_hour"]
    duration    = context.user_data["duration"]
    end_hour    = start_hour + duration

    preview = (
        "✅ *Confirm booking:*\n\n"
        f"📋 Title: *{title}*\n"
        f"📅 Date:  {chosen_date}\n"
        f"🕐 Time:  {start_hour:02d}:00 – {end_hour:02d}:00 ({duration}h)\n"
        f"👤 You:   @{update.effective_user.username or update.effective_user.first_name}"
    )
    await update.message.reply_text(
        preview,
        parse_mode="Markdown",
        reply_markup=_confirm_keyboard(),
    )
    return STATE_CONFIRM


# ── Confirm ───────────────────────────────────────────────────────────────────

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user      = update.effective_user
    username  = user.username or user.first_name
    ud        = context.user_data

    start_time = f"{ud['start_hour']:02d}:00"
    new_booking, conflict = create_booking(
        user_id    = user.id,
        username   = username,
        title      = ud["title"],
        date       = ud["date"],
        start_time = start_time,
        duration   = ud["duration"],
    )

    if conflict:
        await query.edit_message_text(
            f"❌ *Time conflict!*\n\n"
            f"That slot overlaps with an existing booking:\n\n"
            f"{conflict.start_time} – {conflict.end_time}\n"
            f"*{conflict.title}* (@{conflict.username})\n\n"
            "Please try a different time.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← Menu", callback_data="menu")]
            ]),
        )
        return ConversationHandler.END

    # ── Success ──
    await query.edit_message_text(
        f"🎉 *Booking confirmed!*\n\n{new_booking.full_text()}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← Menu", callback_data="menu")]
        ]),
    )

    # ── Group notification ──
    if GROUP_CHAT_ID:
        import datetime as _dt
        day_name = _dt.date.fromisoformat(new_booking.date).strftime("%A, %b %d")
        msg = (
            f"📢 *New office booking*\n\n"
            f"📅 {day_name}\n"
            f"🕐 {new_booking.start_time} – {new_booking.end_time}\n\n"
            f"📋 *{new_booking.title}*\n"
            f"👤 Organiser: @{new_booking.username}"
        )
        try:
            await context.bot.send_message(
                chat_id    = GROUP_CHAT_ID,
                text       = msg,
                parse_mode = "Markdown",
            )
        except Exception as exc:
            logger.warning("Could not send group notification: %s", exc)

    context.user_data.clear()
    return ConversationHandler.END


# ── Cancel flow ───────────────────────────────────────────────────────────────

async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "Booking cancelled. What would you like to do?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← Menu", callback_data="menu")]
        ]),
    )
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────

def register(application) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_entry, pattern="^book$")],
        states={
            STATE_PICK_DATE: [
                CallbackQueryHandler(pick_date,    pattern=r"^date:"),
                CallbackQueryHandler(book_cancel,  pattern="^book_cancel$"),
            ],
            STATE_PICK_HOUR: [
                CallbackQueryHandler(pick_hour,    pattern=r"^hour:"),
                CallbackQueryHandler(pick_hour,    pattern="^hour_busy$"),
                CallbackQueryHandler(back_to_date, pattern="^back_to_date$"),
                CallbackQueryHandler(book_cancel,  pattern="^book_cancel$"),
            ],
            STATE_PICK_DURATION: [
                CallbackQueryHandler(pick_duration, pattern=r"^dur:"),
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
