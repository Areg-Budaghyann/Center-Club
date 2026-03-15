"""
handlers/mybookings.py
-----------------------
My bookings: list, cancel, and edit flows.

Edit flow (inline):
  User selects a booking → sees options → picks "Edit" →
  picks a field (title / date / start time / duration) →
  enters new value → confirmed.
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

import database as db
from config import (
    OFFICE_OPEN,
    OFFICE_CLOSE,
    MIN_DURATION_HOURS,
    MAX_DURATION_HOURS,
    STATE_EDIT_PICK_FIELD,
    STATE_EDIT_ENTER_VALUE,
)
from services.booking_service import cancel_booking, edit_booking

logger = logging.getLogger(__name__)

_BACK_MENU = InlineKeyboardMarkup([[InlineKeyboardButton("← Menu", callback_data="menu")]])


# ── List bookings ─────────────────────────────────────────────────────────────

async def mybookings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    bookings = db.get_user_bookings(user_id)

    if not bookings:
        await query.edit_message_text(
            "📌 *My bookings*\n\nYou have no upcoming bookings.",
            parse_mode="Markdown",
            reply_markup=_BACK_MENU,
        )
        return

    buttons = []
    for b in bookings:
        label = f"{b.date} {b.start_time}–{b.end_time} | {b.title}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"myb_view:{b.id}")])
    buttons.append([InlineKeyboardButton("← Menu", callback_data="menu")])

    await query.edit_message_text(
        "📌 *My bookings* — tap one to manage it:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── View single booking ───────────────────────────────────────────────────────

async def view_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split(":")[1])
    b = db.get_booking_by_id(booking_id)
    if not b:
        await query.answer("Booking not found.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit",   callback_data=f"myb_edit:{b.id}"),
            InlineKeyboardButton("🗑 Cancel", callback_data=f"myb_cancel:{b.id}"),
        ],
        [InlineKeyboardButton("← My bookings", callback_data="mybookings")],
    ])
    await query.edit_message_text(
        b.full_text(),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Cancel booking ────────────────────────────────────────────────────────────

async def cancel_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    booking_id  = int(query.data.split(":")[1])
    user_id     = update.effective_user.id

    ok, reason = cancel_booking(booking_id, user_id)
    if ok:
        await query.edit_message_text(
            "✅ Booking cancelled.",
            reply_markup=_BACK_MENU,
        )
    else:
        await query.edit_message_text(
            f"❌ Could not cancel: {reason}",
            reply_markup=_BACK_MENU,
        )


# ── Edit booking — pick field ─────────────────────────────────────────────────

async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split(":")[1])
    context.user_data["edit_booking_id"] = booking_id

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Title",      callback_data="edit_field:title")],
        [InlineKeyboardButton("📅 Date",       callback_data="edit_field:date")],
        [InlineKeyboardButton("🕐 Start time", callback_data="edit_field:start_time")],
        [InlineKeyboardButton("⏱ Duration",   callback_data="edit_field:duration")],
        [InlineKeyboardButton("← Back",        callback_data=f"myb_view:{booking_id}")],
    ])
    await query.edit_message_text(
        "✏️ *Edit booking* — what would you like to change?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return STATE_EDIT_PICK_FIELD


async def edit_pick_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":")[1]
    context.user_data["edit_field"] = field
    booking_id = context.user_data["edit_booking_id"]
    b = db.get_booking_by_id(booking_id)

    if field == "duration":
        # Inline buttons for duration
        buttons = []
        row = []
        for d in range(MIN_DURATION_HOURS, MAX_DURATION_HOURS + 1):
            row.append(InlineKeyboardButton(f"{d}h", callback_data=f"edit_dur:{d}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("← Back", callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            f"Current duration: *{b.duration}h*\n\nPick new duration:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    elif field == "start_time":
        buttons, row = [], []
        for h in range(OFFICE_OPEN, OFFICE_CLOSE):
            row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"edit_hour:{h}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("← Back", callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            f"Current start: *{b.start_time}*\n\nPick new start time:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    elif field == "date":
        today = date.today()
        buttons, row = [], []
        for i in range(14):
            d = today + timedelta(days=i)
            label = d.strftime("%a %d %b")
            row.append(InlineKeyboardButton(label, callback_data=f"edit_date:{d.isoformat()}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("← Back", callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            f"Current date: *{b.date}*\n\nPick new date:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    else:  # title — free text input
        await query.edit_message_text(
            f"Current title: *{b.title}*\n\nType the new title:",
            parse_mode="Markdown",
        )
        return STATE_EDIT_ENTER_VALUE


async def edit_enter_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle free-text input for editing the title."""
    field      = context.user_data.get("edit_field")
    booking_id = context.user_data.get("edit_booking_id")
    user_id    = update.effective_user.id

    if field != "title":
        await update.message.reply_text("Unexpected input. Please use the buttons.")
        return STATE_EDIT_ENTER_VALUE

    new_title = update.message.text.strip()
    if not new_title or len(new_title) > 80:
        await update.message.reply_text("Invalid title (1–80 characters). Try again.")
        return STATE_EDIT_ENTER_VALUE

    updated, reason = edit_booking(booking_id, user_id, title=new_title)
    if updated:
        await update.message.reply_text(
            f"✅ Title updated!\n\n{updated.full_text()}",
            parse_mode="Markdown",
            reply_markup=_BACK_MENU,
        )
    else:
        await update.message.reply_text(f"❌ {reason}", reply_markup=_BACK_MENU)
    return ConversationHandler.END


async def edit_inline_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline button responses for editing date / start_time / duration."""
    query = update.callback_query
    await query.answer()
    booking_id = context.user_data.get("edit_booking_id")
    user_id    = update.effective_user.id

    data = query.data
    if data.startswith("edit_dur:"):
        new_val = int(data.split(":")[1])
        updated, reason = edit_booking(booking_id, user_id, duration=new_val)
    elif data.startswith("edit_hour:"):
        new_h = int(data.split(":")[1])
        updated, reason = edit_booking(booking_id, user_id, start_time=f"{new_h:02d}:00")
    elif data.startswith("edit_date:"):
        new_date = data.split(":")[1]
        updated, reason = edit_booking(booking_id, user_id, date=new_date)
    else:
        await query.edit_message_text("Unknown action.", reply_markup=_BACK_MENU)
        return ConversationHandler.END

    if updated:
        await query.edit_message_text(
            f"✅ Updated!\n\n{updated.full_text()}",
            parse_mode="Markdown",
            reply_markup=_BACK_MENU,
        )
    else:
        await query.edit_message_text(
            f"❌ {reason}",
            parse_mode="Markdown",
            reply_markup=_BACK_MENU,
        )
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("edit_booking_id", None)
    context.user_data.pop("edit_field", None)
    await query.edit_message_text("Edit cancelled.", reply_markup=_BACK_MENU)
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────

def register(application) -> None:
    # Simple (non-conversation) handlers
    application.add_handler(CallbackQueryHandler(mybookings_entry,      pattern="^mybookings$"))
    application.add_handler(CallbackQueryHandler(view_booking,          pattern=r"^myb_view:"))
    application.add_handler(CallbackQueryHandler(cancel_booking_handler, pattern=r"^myb_cancel:"))

    # Edit conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_entry, pattern=r"^myb_edit:")],
        states={
            STATE_EDIT_PICK_FIELD: [
                CallbackQueryHandler(edit_pick_field, pattern=r"^edit_field:"),
            ],
            STATE_EDIT_ENTER_VALUE: [
                # Inline button values (date / hour / duration)
                CallbackQueryHandler(edit_inline_value, pattern=r"^edit_(dur|hour|date):"),
                # Free text (title)
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_enter_value),
            ],
        },
        fallbacks=[CallbackQueryHandler(edit_cancel, pattern="^menu$")],
        per_message=False,
    )
    application.add_handler(edit_conv)
