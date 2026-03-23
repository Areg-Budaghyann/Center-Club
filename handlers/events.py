"""
handlers/events.py
------------------
Special events feature.

Admin flow (/addevent):
  Pick month → Pick start day → Pick end day (same month) →
  Enter title → Enter description (optional) → Enter location → Confirm

All users:
  🎉 Special events button → view upcoming events
"""

import calendar
import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters,
)

import database as db
from config import ADMIN_IDS
from translations import get_text, DEFAULT_LANG, MONTH_SHORT, WEEKDAY_HEADERS

logger = logging.getLogger(__name__)

# States: month → start day → end day → title → desc → location → confirm
(S_MONTH, S_START_DAY, S_END_DAY,
 S_TITLE, S_DESC, S_LOCATION, S_CONFIRM) = range(7)

CANCEL_CB  = "ev_cancel"
NOOP_CB    = "ev_noop"
SKIP_CB    = "ev_skip_desc"


def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _cancel_row(back_cb: str = None) -> list:
    row = []
    if back_cb:
        row.append(InlineKeyboardButton("← Back", callback_data=back_cb))
    row.append(InlineKeyboardButton("✖ Cancel", callback_data=CANCEL_CB))
    return [row]


def _kb_month(lang: str) -> InlineKeyboardMarkup:
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"ev_month:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows += _cancel_row()
    return InlineKeyboardMarkup(rows)


def _kb_day(year: int, month: int, lang: str, cb_prefix: str, back_cb: str) -> tuple[InlineKeyboardMarkup, str]:
    today = date.today()
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"
    headers = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    rows = [[InlineKeyboardButton(h, callback_data=NOOP_CB) for h in headers]]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=NOOP_CB))
            else:
                d = date(year, month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(str(day_num), callback_data=NOOP_CB))
                else:
                    row.append(InlineKeyboardButton(
                        f"[{day_num}]" if d == today else str(day_num),
                        callback_data=f"{cb_prefix}:{d.isoformat()}"
                    ))
        rows.append(row)
    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows), month_label


def _kb_text_input(back_cb: str, skip: bool = False) -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for text input — only Back and optionally Skip."""
    rows = []
    if skip:
        rows.append([InlineKeyboardButton("⏭ Skip", callback_data=SKIP_CB)])
    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _edit(query, text: str, kb: InlineKeyboardMarkup = None):
    """Edit current message. Silently ignore if nothing changed."""
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except Exception:
        pass


async def _delete_msg(bot, chat_id: int, msg_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


def _header(ud: dict) -> str:
    """Build running header showing what's been chosen so far."""
    parts = []
    if ud.get("ev_year"):
        parts.append(f"📅 {MONTH_SHORT.get(ud.get('_lang','en'), MONTH_SHORT['en'])[ud['ev_month']-1]} {ud['ev_year']}")
    if ud.get("ev_date_start"):
        parts.append(f"▶ {ud['ev_date_start']}")
    if ud.get("ev_date_end"):
        parts.append(f"– {ud['ev_date_end']}")
    if ud.get("ev_title"):
        parts.append(f"📌 {ud['ev_title']}")
    return "  ".join(parts)


# ── View events (all users) ────────────────────────────────────────────────────

def _events_text(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    events = db.get_all_special_events()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]])
    if not events:
        return "🎉 No upcoming special events.", kb

    lines = ["🎉 Upcoming special events\n"]
    for e in events:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 {e['title']}")
        lines.append(f"📅 {e['event_date']}")
        if e.get("event_time"):
            lines.append(f"🕐 {e['event_time']}")
        lines.append(f"📍 {e['location']}")
        if e.get("description"):
            lines.append(f"📝 {e['description']}")
    return "\n".join(lines), kb


async def events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text, kb = _events_text(_lang(context))
    await query.edit_message_text(text, reply_markup=kb)


# ── Admin: /addevent ───────────────────────────────────────────────────────────

async def addevent_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END

    lang = _lang(context)

    # Delete the command message
    try:
        await update.message.delete()
    except Exception:
        pass

    # Clear previous event data but keep lang
    for key in list(context.user_data.keys()):
        if key.startswith("ev_"):
            del context.user_data[key]
    context.user_data["_lang"] = lang

    msg = await update.effective_chat.send_message(
        "📅 Step 1 — Choose month:",
        reply_markup=_kb_month(lang),
    )
    context.user_data["ev_msg_id"] = msg.message_id
    return S_MONTH


# Step 1 — Month
async def ev_pick_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_year"]  = year
    context.user_data["ev_month"] = month

    kb, month_label = _kb_day(year, month, lang, "ev_start_day", None)
    await _edit(query, f"📅 {month_label}\n\nStep 2 — Choose START day:", kb)
    return S_START_DAY


# Step 2 — Start day
async def ev_pick_start_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    start = query.data.split(":")[1]
    context.user_data["ev_date_start"] = start

    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    kb, month_label = _kb_day(year, month, lang, "ev_end_day", "ev_back_to_start")
    await _edit(query, f"📅 {month_label}  ▶ Start: {start}\n\nStep 3 — Choose END day:", kb)
    return S_END_DAY


# Back to start day
async def ev_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    kb, month_label = _kb_day(year, month, lang, "ev_start_day", None)
    await _edit(query, f"📅 {month_label}\n\nStep 2 — Choose START day:", kb)
    return S_START_DAY


# Step 3 — End day
async def ev_pick_end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang      = _lang(context)
    end       = query.data.split(":")[1]
    start     = context.user_data["ev_date_start"]

    if end < start:
        await query.answer("⚠️ End date must be same or after start date", show_alert=True)
        return S_END_DAY

    context.user_data["ev_date_end"] = end
    date_range = start if start == end else f"{start} – {end}"
    context.user_data["ev_date"] = date_range

    kb = _kb_text_input(back_cb="ev_back_to_end")
    msg = await _edit(query, f"📅 {date_range}\n\n✏️ Step 4 — Enter event title:", kb)
    return S_TITLE


# Back to end day
async def ev_back_to_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    start = context.user_data["ev_date_start"]
    kb, month_label = _kb_day(year, month, lang, "ev_end_day", "ev_back_to_start")
    await _edit(query, f"📅 {month_label}  ▶ Start: {start}\n\nStep 3 — Choose END day:", kb)
    return S_END_DAY


# Step 4 — Title
async def ev_enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang  = _lang(context)
    title = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    if not title or len(title) > 100:
        return S_TITLE

    context.user_data["ev_title"] = title
    date_range = context.user_data["ev_date"]
    msg_id     = context.user_data.get("ev_msg_id")

    kb = _kb_text_input(back_cb="ev_back_to_title", skip=True)
    text = f"📅 {date_range}\n📌 {title}\n\n✏️ Step 5 — Enter description (or skip):"
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=text,
            reply_markup=kb,
        )
    except Exception:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=kb
        )
        context.user_data["ev_msg_id"] = msg.message_id
    return S_DESC


# Back to title (from desc step)
async def ev_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_range = context.user_data["ev_date"]
    kb = _kb_text_input(back_cb="ev_back_to_end")
    await _edit(query, f"📅 {date_range}\n\n✏️ Step 4 — Enter event title:", kb)
    return S_TITLE


# Step 5 — Description (optional)
async def ev_enter_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    desc = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    context.user_data["ev_desc"] = desc
    return await _show_location_step(update.effective_chat.id, context)


async def ev_skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["ev_desc"] = ""
    return await _show_location_step(query.message.chat_id, context)


async def _show_location_step(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> int:
    date_range = context.user_data["ev_date"]
    title      = context.user_data["ev_title"]
    msg_id     = context.user_data.get("ev_msg_id")
    kb = _kb_text_input(back_cb="ev_back_to_desc")
    text = f"📅 {date_range}\n📌 {title}\n\n📍 Step 6 — Enter location:"
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb
        )
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
        context.user_data["ev_msg_id"] = msg.message_id
    return S_LOCATION


# Back to desc from location
async def ev_back_to_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_range = context.user_data["ev_date"]
    title      = context.user_data["ev_title"]
    kb = _kb_text_input(back_cb="ev_back_to_title", skip=True)
    await _edit(query, f"📅 {date_range}\n📌 {title}\n\n✏️ Step 5 — Enter description (or skip):", kb)
    return S_DESC


# Step 6 — Location
async def ev_enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang     = _lang(context)
    location = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    context.user_data["ev_location"] = location
    date_range = context.user_data["ev_date"]
    title      = context.user_data["ev_title"]
    desc       = context.user_data.get("ev_desc", "")
    msg_id     = context.user_data.get("ev_msg_id")

    preview = (
        f"✅ Confirm new event:\n\n"
        f"📌 {title}\n"
        f"📅 {date_range}\n"
        f"📍 {location}"
        + (f"\n📝 {desc}" if desc else "")
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save",   callback_data="ev_save"),
        InlineKeyboardButton("✖ Cancel", callback_data=CANCEL_CB),
    ]])
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=msg_id,
            text=preview, reply_markup=kb
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=preview, reply_markup=kb
        )
    context.user_data["ev_ready"] = True
    return S_CONFIRM


# Confirm — Save
async def ev_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    title      = context.user_data["ev_title"]
    date_range = context.user_data["ev_date"]
    location   = context.user_data["ev_location"]
    desc       = context.user_data.get("ev_desc", "")

    event_id = db.create_special_event(
        title=title, event_date=date_range,
        event_time="", location=location, description=desc,
    )
    logger.info("Special event created id=%d", event_id)
    await query.edit_message_text("🎉 Event saved!")
    # Auto-delete the confirmation message after 3 seconds
    import asyncio
    async def _del():
        await asyncio.sleep(3)
        try:
            await query.message.delete()
        except Exception:
            pass
    asyncio.ensure_future(_del())

    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


# Cancel from anywhere
async def ev_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import asyncio
    async def _del_msg(bot, chat_id, msg_id):
        await asyncio.sleep(3)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Event creation cancelled.")
        asyncio.ensure_future(_del_msg(
            update.callback_query.get_bot(),
            update.callback_query.message.chat_id,
            update.callback_query.message.message_id,
        ))
    else:
        try:
            await update.message.delete()
        except Exception:
            pass
        msg = await update.effective_chat.send_message("❌ Event creation cancelled.")
        asyncio.ensure_future(_del_msg(update.get_bot(), msg.chat_id, msg.message_id))
    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


async def ev_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return None


# ── Admin: /delevents ──────────────────────────────────────────────────────────

async def delevents_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    try:
        await update.message.delete()
    except Exception:
        pass

    events = db.get_all_special_events()
    if not events:
        await update.effective_chat.send_message("No events to delete.")
        return

    rows = [[InlineKeyboardButton(
        f"🗑 {e['title']} ({e['event_date']})",
        callback_data=f"ev_del:{e['id']}"
    )] for e in events]
    rows.append([InlineKeyboardButton("← Cancel", callback_data="ev_delcancel")])
    await update.effective_chat.send_message(
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
    await query.edit_message_text("✅ Event deleted.")


# ── Registration ───────────────────────────────────────────────────────────────

def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(events_callback,   pattern="^events$"))
    application.add_handler(CallbackQueryHandler(delevents_confirm, pattern=r"^ev_del(:|cancel)"))

    conv = ConversationHandler(
        entry_points=[CommandHandler("addevent", addevent_start)],
        states={
            S_MONTH: [
                CallbackQueryHandler(ev_pick_month,    pattern=r"^ev_month:\d+:\d+$"),
                CallbackQueryHandler(ev_cancel,        pattern=f"^{CANCEL_CB}$"),
            ],
            S_START_DAY: [
                CallbackQueryHandler(ev_pick_start_day, pattern=r"^ev_start_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_noop,            pattern=f"^{NOOP_CB}$"),
                CallbackQueryHandler(ev_cancel,          pattern=f"^{CANCEL_CB}$"),
            ],
            S_END_DAY: [
                CallbackQueryHandler(ev_pick_end_day,   pattern=r"^ev_end_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_back_to_start,  pattern="^ev_back_to_start$"),
                CallbackQueryHandler(ev_noop,            pattern=f"^{NOOP_CB}$"),
                CallbackQueryHandler(ev_cancel,          pattern=f"^{CANCEL_CB}$"),
            ],
            S_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_title),
                CallbackQueryHandler(ev_back_to_end,   pattern="^ev_back_to_end$"),
                CallbackQueryHandler(ev_cancel,        pattern=f"^{CANCEL_CB}$"),
            ],
            S_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_desc),
                CallbackQueryHandler(ev_skip_desc,     pattern=f"^{SKIP_CB}$"),
                CallbackQueryHandler(ev_back_to_title, pattern="^ev_back_to_title$"),
                CallbackQueryHandler(ev_cancel,        pattern=f"^{CANCEL_CB}$"),
            ],
            S_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_location),
                CallbackQueryHandler(ev_back_to_desc,  pattern="^ev_back_to_desc$"),
                CallbackQueryHandler(ev_cancel,        pattern=f"^{CANCEL_CB}$"),
            ],
            S_CONFIRM: [
                CallbackQueryHandler(ev_save,   pattern="^ev_save$"),
                CallbackQueryHandler(ev_cancel, pattern=f"^{CANCEL_CB}$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", ev_cancel),
            CallbackQueryHandler(ev_cancel, pattern=f"^{CANCEL_CB}$"),
        ],
        per_message=False,
    )
    application.add_handler(conv)
    application.add_handler(CommandHandler("delevents", delevents_start))
