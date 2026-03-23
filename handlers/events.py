"""
handlers/events.py
------------------
Special events feature.

Admin flow (/addevent):
  Pick month → Pick day → Pick start hour → Pick end hour →
  Enter title → Enter description → Confirm
  All bot messages are edited in place. User messages auto-deleted.

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

# Conversation states
(S_MONTH, S_DAY, S_END_MONTH, S_END_DAY,
 S_START_HOUR, S_END_HOUR,
 S_TITLE, S_DESC, S_CONFIRM) = range(9)


def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _et(lang: str, key: str) -> str:
    """Get text with fallback for events-specific keys."""
    fallbacks = {
        "en": {
            "btn_events":    "🎉 Special events",
            "events_title":  "Upcoming special events",
            "events_empty":  "No upcoming special events.",
            "ev_pick_month": "📅 Step 1 — Choose month:",
            "ev_pick_day":   "📅 {month} — choose day:",
            "ev_pick_start": "📅 {date}\n\n🕐 Step 3 — Choose start time:",
            "ev_pick_end":   "📅 {date}  |  🕐 {start}:00\n\n🕐 Step 4 — Choose end time:",
            "ev_enter_title":"📅 {date}  |  🕐 {start}:00–{end}:00\n\n✏️ Step 5 — Enter event title:",
            "ev_enter_desc": "📅 {date}  |  🕐 {start}:00–{end}:00\n📌 {title}\n\n✏️ Step 6 — Enter description:",
            "ev_confirm":    "✅ Confirm new event:\n\n📌 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00\n📍 {location}\n\n📝 {desc}",
            "ev_saved":      "🎉 Event saved!",
            "ev_cancelled":  "Event creation cancelled.",
        },
        "ru": {
            "btn_events":    "🎉 Спец. события",
            "events_title":  "Предстоящие события",
            "events_empty":  "Нет предстоящих событий.",
            "ev_pick_month": "📅 Шаг 1 — Выберите месяц:",
            "ev_pick_day":   "📅 {month} — выберите день:",
            "ev_pick_start": "📅 {date}\n\n🕐 Шаг 3 — Выберите время начала:",
            "ev_pick_end":   "📅 {date}  |  🕐 {start}:00\n\n🕐 Шаг 4 — Выберите время конца:",
            "ev_enter_title":"📅 {date}  |  🕐 {start}:00–{end}:00\n\n✏️ Шаг 5 — Введите название:",
            "ev_enter_desc": "📅 {date}  |  🕐 {start}:00–{end}:00\n📌 {title}\n\n✏️ Шаг 6 — Введите описание:",
            "ev_confirm":    "✅ Подтвердите новое событие:\n\n📌 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00\n📍 {location}\n\n📝 {desc}",
            "ev_saved":      "🎉 Событие сохранено!",
            "ev_cancelled":  "Создание события отменено.",
        },
        "hy": {
            "btn_events":    "🎉 Hатук ирадарцутюннер",
            "events_title":  "Аджика hатук ирадарцутюннер",
            "events_empty":  "Аджика hатук ирадарцутюннер чка.",
            "ev_pick_month": "📅 Кайл 1 — Ынтреk амист:",
            "ev_pick_day":   "📅 {month} — ынтреk орт:",
            "ev_pick_start": "📅 {date}\n\n🕐 Кайл 3 — Ынтреk мекнарки жамт:",
            "ev_pick_end":   "📅 {date}  |  🕐 {start}:00\n\n🕐 Кайл 4 — Ынтреk авартри жамт:",
            "ev_enter_title":"📅 {date}  |  🕐 {start}:00–{end}:00\n\n✏️ Кайл 5 — Мутqагреk ануnt:",
            "ev_enter_desc": "📅 {date}  |  🕐 {start}:00–{end}:00\n📌 {title}\n\n✏️ Кайл 6 — Мутqагреk нкарагрумт:",
            "ev_confirm":    "✅ Хастател нор ирадарцутюнт:\n\n📌 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00\n📍 {location}\n\n📝 {desc}",
            "ev_saved":      "🎉 Ирадарцутюнт пахпанвад е!",
            "ev_cancelled":  "Ирадарцутюни стегцумт чегаркvад е.",
        },
    }
    try:
        result = get_text(lang, key)
        if not result.startswith("[missing"):
            return result
    except Exception:
        pass
    return fallbacks.get(lang, fallbacks["en"]).get(key, key)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _kb_ev_month(lang: str) -> InlineKeyboardMarkup:
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"ev_month:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_ev_day(year: int, month: int, lang: str):
    today = date.today()
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"
    headers = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    rows = [[InlineKeyboardButton(h, callback_data="ev_noop") for h in headers]]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ev_noop"))
            else:
                d = date(year, month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(str(day_num), callback_data="ev_noop"))
                elif d == today:
                    row.append(InlineKeyboardButton(f"[{day_num}]", callback_data=f"ev_day:{d.isoformat()}"))
                else:
                    row.append(InlineKeyboardButton(str(day_num), callback_data=f"ev_day:{d.isoformat()}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data="ev_back_month")])
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel")])
    return InlineKeyboardMarkup(rows), month_label


def _kb_ev_hour(lang: str, callback_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for h in range(0, 24):
        row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"{callback_prefix}:{h}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data=back_cb)])
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel")])
    return InlineKeyboardMarkup(rows)


# ── View events (all users) ───────────────────────────────────────────────────

def _events_text(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    events = db.get_all_special_events()
    if not events:
        text = _et(lang, "events_empty")
        kb   = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]])
        return text, kb

    lines = ["🎉 " + _et(lang, "events_title") + "\n"]
    for e in events:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 {e['title']}")
        lines.append(f"📅 {e['event_date']}")
        lines.append(f"🕐 {e['event_time']}")
        lines.append(f"📍 {e['location']}")
        if e.get('description'):
            lines.append(f"📝 {e['description']}")

    kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]])
    return "\n".join(lines), kb


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

    lang = _lang(context)
    # Delete the /addevent command message
    try: await update.message.delete()
    except Exception: pass

    msg = await update.effective_chat.send_message(
        _et(lang, "ev_pick_month"),
        reply_markup=_kb_ev_month(lang),
    )
    context.user_data["ev_msg_id"] = msg.message_id
    return S_MONTH


async def ev_pick_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_year"]  = year
    context.user_data["ev_month"] = month

    keyboard, month_label = _kb_ev_day(year, month, lang)
    await query.edit_message_text(
        _et(lang, "ev_pick_day").format(month=month_label),
        reply_markup=keyboard,
    )
    return S_DAY


async def ev_back_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    await query.edit_message_text(_et(lang, "ev_pick_month"), reply_markup=_kb_ev_month(lang))
    return S_MONTH



def _kb_ev_end_month(lang: str) -> InlineKeyboardMarkup:
    today = date.today()
    rows, row = [], []
    for month in range(today.month, 13):
        label = MONTH_SHORT[lang][month - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"ev_end_month:{today.year}:{month}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data="ev_back_to_start_day")])
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel")])
    return InlineKeyboardMarkup(rows)


def _kb_ev_end_day(year: int, month: int, lang: str, start_date: str):
    today = date.today()
    from datetime import date as _date
    start = _date.fromisoformat(start_date)
    month_label = f"{MONTH_SHORT[lang][month - 1]} {year}"
    headers = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    rows = [[InlineKeyboardButton(h, callback_data="ev_noop") for h in headers]]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ev_noop"))
            else:
                d = _date(year, month, day_num)
                if d < start:
                    row.append(InlineKeyboardButton(str(day_num), callback_data="ev_noop"))
                else:
                    row.append(InlineKeyboardButton(str(day_num), callback_data=f"ev_end_day:{d.isoformat()}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data="ev_back_end_month")])
    rows.append([InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel")])
    return InlineKeyboardMarkup(rows), month_label

async def ev_pick_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    chosen_date = query.data.split(":")[1]
    context.user_data["ev_date_start"] = chosen_date

    # Now pick end month
    await query.edit_message_text(
        f"✅ Start date: {chosen_date}\n\n📅 Step 2 — Choose END month:",
        reply_markup=_kb_ev_end_month(lang),
    )
    return S_END_MONTH



async def ev_pick_end_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_end_year"]  = year
    context.user_data["ev_end_month"] = month
    start_date = context.user_data["ev_date_start"]

    keyboard, month_label = _kb_ev_end_day(year, month, lang, start_date)
    await query.edit_message_text(
        f"✅ Start date: {start_date}\n\n📅 {month_label} — choose END day:",
        reply_markup=keyboard,
    )
    return S_END_DAY


async def ev_back_end_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    start_date = context.user_data["ev_date_start"]
    await query.edit_message_text(
        f"✅ Start date: {start_date}\n\n📅 Step 2 — Choose END month:",
        reply_markup=_kb_ev_end_month(lang),
    )
    return S_END_MONTH


async def ev_back_to_start_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    keyboard, month_label = _kb_ev_day(year, month, lang)
    await query.edit_message_text(
        _et(lang, "ev_pick_day").format(month=month_label),
        reply_markup=keyboard,
    )
    return S_DAY


async def ev_pick_end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    end_date    = query.data.split(":")[1]
    start_date  = context.user_data["ev_date_start"]
    context.user_data["ev_date_end"] = end_date

    await query.edit_message_text(
        _et(lang, "ev_pick_start").format(date=f"{start_date} – {end_date}"),
        reply_markup=_kb_ev_hour(lang, "ev_start", "ev_back_end_month"),
    )
    return S_START_HOUR

async def ev_pick_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    start_h = int(query.data.split(":")[1])
    context.user_data["ev_start"] = start_h
    start_date = context.user_data["ev_date_start"]
    end_date   = context.user_data["ev_date_end"]
    chosen_date = f"{start_date} – {end_date}"
    context.user_data["ev_date"] = chosen_date

    await query.edit_message_text(
        _et(lang, "ev_pick_end").format(date=chosen_date, start=f"{start_h:02d}"),
        reply_markup=_kb_ev_hour(lang, "ev_end", "ev_back_start"),
    )
    return S_END_HOUR


async def ev_back_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    chosen_date = context.user_data["ev_date"]
    await query.edit_message_text(
        _et(lang, "ev_pick_start").format(date=chosen_date),
        reply_markup=_kb_ev_hour(lang, "ev_start", "ev_back_month"),
    )
    return S_START_HOUR


async def ev_pick_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    end_h = int(query.data.split(":")[1])
    start_h = context.user_data["ev_start"]

    if end_h <= start_h:
        await query.answer("⚠️ End time must be after start time", show_alert=True)
        return S_END_HOUR

    context.user_data["ev_end"] = end_h
    chosen_date = context.user_data["ev_date"]

    msg = await query.edit_message_text(
        _et(lang, "ev_enter_title").format(
            date=chosen_date,
            start=f"{start_h:02d}",
            end=f"{end_h:02d}"
        ),
    )
    context.user_data["ev_msg_id"] = msg.message_id
    return S_TITLE


async def ev_enter_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    title = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass

    if not title or len(title) > 100:
        return S_TITLE

    context.user_data["ev_title"] = title
    chosen_date = context.user_data["ev_date"]
    start_h = context.user_data["ev_start"]
    end_h   = context.user_data["ev_end"]
    msg_id  = context.user_data.get("ev_msg_id")

    text = _et(lang, "ev_enter_desc").format(
        date=chosen_date,
        start=f"{start_h:02d}",
        end=f"{end_h:02d}",
        title=title,
    )

    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=text,
        )
    except Exception:
        msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        context.user_data["ev_msg_id"] = msg.message_id
    return S_DESC


async def ev_enter_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    desc = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass

    context.user_data["ev_desc"] = desc
    chosen_date = context.user_data["ev_date"]
    start_h = context.user_data["ev_start"]
    end_h   = context.user_data["ev_end"]
    title   = context.user_data["ev_title"]
    msg_id  = context.user_data.get("ev_msg_id")

    # Ask for location
    text = f"📅 {chosen_date}  |  🕐 {start_h:02d}:00–{end_h:02d}:00\n📌 {title}\n\n📍 Step 7 — Enter location:"
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=text,
        )
    except Exception:
        msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        context.user_data["ev_msg_id"] = msg.message_id
    return S_CONFIRM  # reuse S_CONFIRM state for location input


async def ev_enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    location = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass

    context.user_data["ev_location"] = location
    chosen_date = context.user_data["ev_date"]
    start_h = context.user_data["ev_start"]
    end_h   = context.user_data["ev_end"]
    title   = context.user_data["ev_title"]
    desc    = context.user_data["ev_desc"]
    msg_id  = context.user_data.get("ev_msg_id")

    preview = _et(lang, "ev_confirm").format(
        title=title,
        date=chosen_date,
        start=f"{start_h:02d}",
        end=f"{end_h:02d}",
        location=location,
        desc=desc,
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save", callback_data="ev_save"),
        InlineKeyboardButton("✖ Cancel", callback_data="ev_cancel"),
    ]])

    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=preview,
            reply_markup=kb,
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=preview,
            reply_markup=kb,
        )

    # Reuse S_CONFIRM state — but we need a new state for this final step
    # Store that we're in location-confirmed state
    context.user_data["ev_ready"] = True
    return S_CONFIRM


async def ev_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)

    if not context.user_data.get("ev_ready"):
        return S_CONFIRM

    title    = context.user_data["ev_title"]
    date_str = context.user_data["ev_date"]
    start_h  = context.user_data["ev_start"]
    end_h    = context.user_data["ev_end"]
    location = context.user_data["ev_location"]
    desc     = context.user_data["ev_desc"]

    event_id = db.create_special_event(
        title      = title,
        event_date = date_str,
        event_time = f"{start_h:02d}:00 – {end_h:02d}:00",
        location   = location,
        description= desc,
    )
    logger.info("Special event created id=%d", event_id)
    await query.edit_message_text(_et(lang, "ev_saved"))
    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


async def ev_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        lang = _lang(context)
        await update.callback_query.edit_message_text(_et(lang, "ev_cancelled"))
    else:
        lang = _lang(context)
        try: await update.message.delete()
        except Exception: pass
        await update.effective_chat.send_message(_et(lang, "ev_cancelled"))
    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    return ConversationHandler.END


async def ev_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return None  # stay in current state


# ── Delete event (admin only) ─────────────────────────────────────────────────

async def delevents_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    try: await update.message.delete()
    except Exception: pass

    events = db.get_all_special_events()
    if not events:
        await update.effective_chat.send_message("No events to delete.")
        return

    rows = []
    for e in events:
        rows.append([InlineKeyboardButton(
            f"🗑 {e['title']} ({e['event_date']})",
            callback_data=f"ev_del:{e['id']}"
        )])
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


# ── Registration ──────────────────────────────────────────────────────────────

def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(events_callback,  pattern="^events$"))
    application.add_handler(CallbackQueryHandler(delevents_confirm, pattern=r"^ev_del(:|cancel)"))

    conv = ConversationHandler(
        entry_points=[CommandHandler("addevent", addevent_start)],
        states={
            S_MONTH: [
                CallbackQueryHandler(ev_pick_month,      pattern=r"^ev_month:\d+:\d+$"),
                CallbackQueryHandler(ev_cancel,          pattern="^ev_cancel$"),
            ],
            S_DAY: [
                CallbackQueryHandler(ev_pick_day,        pattern=r"^ev_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_back_month,      pattern="^ev_back_month$"),
                CallbackQueryHandler(ev_noop,            pattern="^ev_noop$"),
                CallbackQueryHandler(ev_cancel,          pattern="^ev_cancel$"),
            ],
            S_END_MONTH: [
                CallbackQueryHandler(ev_pick_end_month,  pattern=r"^ev_end_month:\d+:\d+$"),
                CallbackQueryHandler(ev_back_to_start_day, pattern="^ev_back_to_start_day$"),
                CallbackQueryHandler(ev_cancel,          pattern="^ev_cancel$"),
            ],
            S_END_DAY: [
                CallbackQueryHandler(ev_pick_end_day,    pattern=r"^ev_end_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_back_end_month,  pattern="^ev_back_end_month$"),
                CallbackQueryHandler(ev_noop,            pattern="^ev_noop$"),
                CallbackQueryHandler(ev_cancel,          pattern="^ev_cancel$"),
            ],
            S_START_HOUR: [
                CallbackQueryHandler(ev_pick_start,      pattern=r"^ev_start:\d+$"),
                CallbackQueryHandler(ev_back_end_month,  pattern="^ev_back_end_month$"),
                CallbackQueryHandler(ev_noop,            pattern="^ev_noop$"),
                CallbackQueryHandler(ev_cancel,          pattern="^ev_cancel$"),
            ],
            S_END_HOUR: [
                CallbackQueryHandler(ev_pick_end,   pattern=r"^ev_end:\d+$"),
                CallbackQueryHandler(ev_back_start, pattern="^ev_back_start$"),
                CallbackQueryHandler(ev_noop,       pattern="^ev_noop$"),
                CallbackQueryHandler(ev_cancel,     pattern="^ev_cancel$"),
            ],
            S_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_title),
                CallbackQueryHandler(ev_cancel, pattern="^ev_cancel$"),
            ],
            S_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_desc),
                CallbackQueryHandler(ev_cancel, pattern="^ev_cancel$"),
            ],
            S_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_location),
                CallbackQueryHandler(ev_save,   pattern="^ev_save$"),
                CallbackQueryHandler(ev_cancel, pattern="^ev_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", ev_cancel),
            CallbackQueryHandler(ev_cancel, pattern="^ev_cancel$"),
        ],
        per_message=False,
    )
    application.add_handler(conv)
    application.add_handler(CommandHandler("delevents", delevents_start))
