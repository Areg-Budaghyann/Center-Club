"""
handlers/mybookings.py
-----------------------
My bookings: list, cancel, and edit flows.
All texts come from translations.get_text().
"""

import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters,
)

import database as db
from config import (
    OFFICE_OPEN, OFFICE_CLOSE,
    MIN_DURATION_HOURS, MAX_DURATION_HOURS,
    STATE_EDIT_PICK_FIELD, STATE_EDIT_ENTER_VALUE,
)
from services.booking_service import cancel_booking, edit_booking
from translations import get_text, DEFAULT_LANG

logger = logging.getLogger(__name__)


def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)

def _back_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")
    ]])


# ── List bookings ─────────────────────────────────────────────────────────────

async def mybookings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang    = _lang(context)
    user_id = update.effective_user.id
    bookings = db.get_user_bookings(user_id)

    if not bookings:
        await query.edit_message_text(
            get_text(lang, "my_bookings_empty"),
            parse_mode="Markdown",
            reply_markup=_back_menu(lang),
        )
        return

    buttons = []
    for b in bookings:
        label = f"{b.date} {b.start_time}–{b.end_time} | {b.title}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"myb_view:{b.id}")])
    buttons.append([InlineKeyboardButton(
        get_text(lang, "btn_delete_all"), callback_data="myb_delete_all_confirm"
    )])
    buttons.append([InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")])

    await query.edit_message_text(
        get_text(lang, "my_bookings_title"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── View single booking ───────────────────────────────────────────────────────

async def view_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang       = _lang(context)
    booking_id = int(query.data.split(":")[1])
    b          = db.get_booking_by_id(booking_id)

    if not b:
        await query.answer(get_text(lang, "booking_not_found"), show_alert=True)
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "btn_edit"),   callback_data=f"myb_edit:{b.id}"),
            InlineKeyboardButton(get_text(lang, "btn_delete"), callback_data=f"myb_cancel:{b.id}"),
        ],
        [InlineKeyboardButton(get_text(lang, "btn_my_bookings_back"), callback_data="mybookings")],
    ])
    await query.edit_message_text(b.full_text(), parse_mode="Markdown", reply_markup=keyboard)


# ── Cancel booking ────────────────────────────────────────────────────────────

async def cancel_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query      = update.callback_query
    await query.answer()
    lang       = _lang(context)
    booking_id = int(query.data.split(":")[1])
    user_id    = update.effective_user.id

    ok, reason = cancel_booking(booking_id, user_id)
    if ok:
        await query.edit_message_text(
            get_text(lang, "booking_deleted"),
            reply_markup=_back_menu(lang),
        )
    else:
        await query.edit_message_text(
            get_text(lang, "booking_delete_failed", reason=reason),
            reply_markup=_back_menu(lang),
        )


# ── Edit booking — pick field ─────────────────────────────────────────────────

async def edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query      = update.callback_query
    await query.answer()
    lang       = _lang(context)
    booking_id = int(query.data.split(":")[1])
    context.user_data["edit_booking_id"] = booking_id

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "btn_edit_title"),      callback_data="edit_field:title")],
        [InlineKeyboardButton(get_text(lang, "btn_edit_date"),       callback_data="edit_field:date")],
        [InlineKeyboardButton(get_text(lang, "btn_edit_start_time"), callback_data="edit_field:start_time")],
        [InlineKeyboardButton(get_text(lang, "btn_edit_duration"),   callback_data="edit_field:duration")],
        [InlineKeyboardButton(get_text(lang, "btn_back"),            callback_data=f"myb_view:{booking_id}")],
    ])
    await query.edit_message_text(
        get_text(lang, "edit_title"),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return STATE_EDIT_PICK_FIELD


async def edit_pick_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query      = update.callback_query
    await query.answer()
    lang       = _lang(context)
    field      = query.data.split(":")[1]
    context.user_data["edit_field"] = field
    booking_id = context.user_data["edit_booking_id"]
    b          = db.get_booking_by_id(booking_id)

    if field == "duration":
        buttons, row = [], []
        for d in range(MIN_DURATION_HOURS, MAX_DURATION_HOURS + 1):
            row.append(InlineKeyboardButton(f"{d}h", callback_data=f"edit_dur:{d}"))
            if len(row) == 3:
                buttons.append(row); row = []
        if row: buttons.append(row)
        buttons.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            get_text(lang, "edit_pick_duration", duration=b.duration),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    elif field == "start_time":
        buttons, row = [], []
        for h in range(OFFICE_OPEN, OFFICE_CLOSE):
            row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"edit_hour:{h}"))
            if len(row) == 4:
                buttons.append(row); row = []
        if row: buttons.append(row)
        buttons.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            get_text(lang, "edit_pick_start_time", start_time=b.start_time),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    elif field == "date":
        today = date.today()
        buttons, row = [], []
        for i in range(14):
            d = today + timedelta(days=i)
            row.append(InlineKeyboardButton(d.strftime("%a %d %b"), callback_data=f"edit_date:{d.isoformat()}"))
            if len(row) == 3:
                buttons.append(row); row = []
        if row: buttons.append(row)
        buttons.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data=f"myb_edit:{booking_id}")])
        await query.edit_message_text(
            get_text(lang, "edit_pick_date", date=b.date),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return STATE_EDIT_ENTER_VALUE

    else:  # title
        await query.edit_message_text(
            get_text(lang, "edit_pick_title", title=b.title),
            parse_mode="Markdown",
        )
        return STATE_EDIT_ENTER_VALUE


async def edit_enter_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field      = context.user_data.get("edit_field")
    booking_id = context.user_data.get("edit_booking_id")
    user_id    = update.effective_user.id
    lang       = _lang(context)

    if field != "title":
        await update.message.reply_text(get_text(lang, "edit_unexpected_input"))
        return STATE_EDIT_ENTER_VALUE

    new_title = update.message.text.strip()
    if not new_title or len(new_title) > 80:
        await update.message.reply_text(get_text(lang, "title_invalid"))
        return STATE_EDIT_ENTER_VALUE

    updated, reason = edit_booking(booking_id, user_id, title=new_title)
    if updated:
        await update.message.reply_text(
            get_text(lang, "edit_title_updated", details=updated.full_text()),
            parse_mode="Markdown",
            reply_markup=_back_menu(lang),
        )
    else:
        await update.message.reply_text(
            get_text(lang, "edit_failed", reason=reason),
            reply_markup=_back_menu(lang),
        )
    return ConversationHandler.END


async def edit_inline_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query      = update.callback_query
    await query.answer()
    booking_id = context.user_data.get("edit_booking_id")
    user_id    = update.effective_user.id
    lang       = _lang(context)
    data       = query.data

    if data.startswith("edit_dur:"):
        updated, reason = edit_booking(booking_id, user_id, duration=int(data.split(":")[1]))
    elif data.startswith("edit_hour:"):
        new_h = int(data.split(":")[1])
        updated, reason = edit_booking(booking_id, user_id, start_time=f"{new_h:02d}:00")
    elif data.startswith("edit_date:"):
        updated, reason = edit_booking(booking_id, user_id, date=data.split(":")[1])
    else:
        await query.edit_message_text(get_text(lang, "edit_unknown_action"), reply_markup=_back_menu(lang))
        return ConversationHandler.END

    if updated:
        await query.edit_message_text(
            get_text(lang, "edit_updated", details=updated.full_text()),
            parse_mode="Markdown",
            reply_markup=_back_menu(lang),
        )
    else:
        await query.edit_message_text(
            get_text(lang, "edit_failed", reason=reason),
            parse_mode="Markdown",
            reply_markup=_back_menu(lang),
        )
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    context.user_data.pop("edit_booking_id", None)
    context.user_data.pop("edit_field", None)
    await query.edit_message_text(get_text(lang, "edit_cancelled"), reply_markup=_back_menu(lang))
    return ConversationHandler.END



# ── Delete all bookings ───────────────────────────────────────────────────────

async def delete_all_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for confirmation before deleting all bookings."""
    query = update.callback_query
    await query.answer()
    lang    = _lang(context)
    user_id = update.effective_user.id
    count   = len(db.get_user_bookings(user_id))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(lang, "btn_delete_all_yes"), callback_data="myb_delete_all_yes"),
            InlineKeyboardButton(get_text(lang, "btn_cancel"),         callback_data="mybookings"),
        ],
    ])
    await query.edit_message_text(
        get_text(lang, "delete_all_confirm", count=count),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def delete_all_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all upcoming bookings for the user."""
    query   = update.callback_query
    await query.answer()
    lang    = _lang(context)
    user_id = update.effective_user.id
    bookings = db.get_user_bookings(user_id)

    deleted = 0
    for b in bookings:
        if db.delete_booking(b.id):
            deleted += 1

    await query.edit_message_text(
        get_text(lang, "delete_all_done", count=deleted),
        parse_mode="Markdown",
        reply_markup=_back_menu(lang),
    )


# ── Registration ──────────────────────────────────────────────────────────────

def register(application) -> None:
    application.add_handler(CallbackQueryHandler(mybookings_entry,       pattern="^mybookings$"))
    application.add_handler(CallbackQueryHandler(view_booking,           pattern=r"^myb_view:"))
    application.add_handler(CallbackQueryHandler(cancel_booking_handler, pattern=r"^myb_cancel:"))
    application.add_handler(CallbackQueryHandler(delete_all_confirm,     pattern="^myb_delete_all_confirm$"))
    application.add_handler(CallbackQueryHandler(delete_all_execute,     pattern="^myb_delete_all_yes$"))

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_entry, pattern=r"^myb_edit:")],
        states={
            STATE_EDIT_PICK_FIELD: [
                CallbackQueryHandler(edit_pick_field, pattern=r"^edit_field:"),
            ],
            STATE_EDIT_ENTER_VALUE: [
                CallbackQueryHandler(edit_inline_value, pattern=r"^edit_(dur|hour|date):"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_enter_value),
            ],
        },
        fallbacks=[CallbackQueryHandler(edit_cancel, pattern="^menu$")],
        per_message=False,
    )
    application.add_handler(edit_conv)