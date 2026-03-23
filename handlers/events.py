"""
handlers/events.py
------------------
Special events feature.

Admin only:
  /addevent  — starts a conversation to add a new special event
  /delevents — shows list of events to delete (admin only)

All users:
  🎉 Special events button in main menu — view all upcoming events
"""

import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters,
)

import database as db
from config import ADMIN_IDS
from translations import get_text, DEFAULT_LANG

logger = logging.getLogger(__name__)

# Conversation states
S_TITLE, S_DATE, S_TIME, S_LOCATION, S_CONFIRM = range(5)


def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _events_text(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Build the events list message and keyboard."""
    events = db.get_all_special_events()

    if not events:
        text = "🎉 " + get_text(lang, "events_empty")
        kb   = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")
        ]])
        return text, kb

    lines = ["🎉 " + get_text(lang, "events_title") + "\n"]
    for e in events:
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 {e['title']}")
        lines.append(f"📅 {e['event_date']}")
        lines.append(f"🕐 {e['event_time']}")
        lines.append(f"📍 {e['location']}")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")
    ]])
    return "\n".join(lines), kb


# ── View events (all users) ───────────────────────────────────────────────────

async def events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    text, kb = _events_text(lang)
    await query.edit_message_text(text, reply_markup=kb)


# ── Add event flow (admin only) ───────────────────────────────────────────────

async def addevent_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📌 New special event\n\nStep 1 of 4 — Enter event title:"
    )
    return S_TITLE


async def addevent_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ev_title"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Step 2 of 4 — Enter event date:\nFormat: YYYY-MM-DD (e.g. 2026-04-15)"
    )
    return S_DATE


async def addevent_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import re
    date_str = update.message.text.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        await update.message.reply_text("❌ Invalid format. Use YYYY-MM-DD (e.g. 2026-04-15):")
        return S_DATE
    context.user_data["ev_date"] = date_str
    await update.message.reply_text(
        "🕐 Step 3 of 4 — Enter event time:\nFormat: HH:MM (e.g. 18:00)"
    )
    return S_TIME


async def addevent_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import re
    time_str = update.message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g. 18:00):")
        return S_TIME
    context.user_data["ev_time"] = time_str
    await update.message.reply_text(
        "📍 Step 4 of 4 — Enter event location:\n(e.g. Center Club, Main Hall)"
    )
    return S_LOCATION


async def addevent_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ev_location"] = update.message.text.strip()

    title    = context.user_data["ev_title"]
    date_str = context.user_data["ev_date"]
    time_str = context.user_data["ev_time"]
    location = context.user_data["ev_location"]

    preview = (
        f"✅ Confirm new event:\n\n"
        f"📌 {title}\n"
        f"📅 {date_str}\n"
        f"🕐 {time_str}\n"
        f"📍 {location}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save", callback_data="ev_confirm"),
        InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel"),
    ]])
    await update.message.reply_text(preview, reply_markup=kb)
    return S_CONFIRM


async def addevent_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "ev_cancel":
        await query.edit_message_text("❌ Event creation cancelled.")
        return ConversationHandler.END

    title    = context.user_data["ev_title"]
    date_str = context.user_data["ev_date"]
    time_str = context.user_data["ev_time"]
    location = context.user_data["ev_location"]

    event_id = db.create_special_event(title, date_str, time_str, location)
    logger.info("Special event created id=%d by admin=%d", event_id, update.effective_user.id)
    await query.edit_message_text(f"🎉 Event saved! (id={event_id})")
    return ConversationHandler.END


async def addevent_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Event creation cancelled.")
    return ConversationHandler.END


# ── Delete event (admin only) ─────────────────────────────────────────────────

async def delevents_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    events = db.get_all_special_events()
    if not events:
        await update.message.reply_text("No events to delete.")
        return

    rows = []
    for e in events:
        rows.append([InlineKeyboardButton(
            f"🗑 {e['title']} ({e['event_date']})",
            callback_data=f"ev_del:{e['id']}"
        )])
    rows.append([InlineKeyboardButton("← Cancel", callback_data="ev_delcancel")])

    await update.message.reply_text(
        "Select an event to delete:",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def delevents_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "ev_delcancel":
        await query.edit_message_text("Cancelled.")
        return

    event_id = int(query.data.split(":")[1])
    db.delete_special_event(event_id)
    await query.edit_message_text(f"✅ Event deleted.")


# ── Registration ──────────────────────────────────────────────────────────────

def register(application: Application) -> None:
    # View events button
    application.add_handler(CallbackQueryHandler(events_callback, pattern="^events$"))

    # Delete event callbacks
    application.add_handler(CallbackQueryHandler(delevents_confirm, pattern=r"^ev_del(:|cancel)"))

    # Add event conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("addevent", addevent_start)],
        states={
            S_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_title)],
            S_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_date)],
            S_TIME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_time)],
            S_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_location)],
            S_CONFIRM:  [CallbackQueryHandler(addevent_confirm, pattern="^ev_(confirm|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", addevent_cancel)],
        per_message=False,
    )
    application.add_handler(conv)
    application.add_handler(CommandHandler("delevents", delevents_start))
