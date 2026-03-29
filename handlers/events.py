"""
handlers/events.py
------------------
Special events - view for all, full admin controls for admins.
"""

import asyncio
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

# ── Add event states ──────────────────────────────────────────────────────────
(S_MONTH, S_START_DAY, S_END_DAY,
 S_TITLE, S_DESC, S_LOCATION, S_CONFIRM) = range(7)

# ── Edit event states ─────────────────────────────────────────────────────────
(SE_MENU, SE_DATE_MONTH, SE_DATE_START, SE_DATE_END,
 SE_TEXT) = range(10, 15)

CANCEL_CB = "ev_cancel"
NOOP_CB   = "ev_noop"
SKIP_CB   = "ev_skip_desc"


def _lang(context) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _auto_del(bot, chat_id, msg_id, delay=3):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _cancel_row(back_cb=None):
    row = []
    if back_cb:
        row.append(InlineKeyboardButton("← Back", callback_data=back_cb))
    row.append(InlineKeyboardButton("✖ Cancel", callback_data=CANCEL_CB))
    return [row]


def _kb_month(lang, cb_prefix="ev_month", back_cb=None):
    today = date.today()
    rows, row = [], []
    for m in range(today.month, 13):
        label = MONTH_SHORT[lang][m - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"{cb_prefix}:{today.year}:{m}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows)


def _kb_month_extended(lang, cb_prefix="ev_month", back_cb=None):
    """Month picker that includes next year's months too."""
    today = date.today()
    rows, row = [], []
    # Current year remaining months
    for m in range(today.month, 13):
        label = MONTH_SHORT[lang][m - 1]
        row.append(InlineKeyboardButton(label, callback_data=f"{cb_prefix}:{today.year}:{m}"))
        if len(row) == 3:
            rows.append(row); row = []
    # Next year months
    for m in range(1, today.month):
        label = MONTH_SHORT[lang][m - 1] + f" {today.year + 1}"
        row.append(InlineKeyboardButton(label, callback_data=f"{cb_prefix}:{today.year + 1}:{m}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows)


def _kb_day(year, month, lang, cb_prefix, back_cb, min_date=None,
            next_month_cb=None, prev_month_cb=None):
    today = date.today()
    min_d = min_date or today
    month_label = f"{MONTH_SHORT[lang][month-1]} {year}"
    headers = WEEKDAY_HEADERS.get(lang, WEEKDAY_HEADERS["en"])
    rows = [[InlineKeyboardButton(h, callback_data=NOOP_CB) for h in headers]]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=NOOP_CB))
            else:
                d = date(year, month, day_num)
                if d < min_d:
                    row.append(InlineKeyboardButton(str(day_num), callback_data=NOOP_CB))
                else:
                    label = f"[{day_num}]" if d == today else str(day_num)
                    row.append(InlineKeyboardButton(label, callback_data=f"{cb_prefix}:{d.isoformat()}"))
        rows.append(row)

    # Month navigation
    nav = []
    if prev_month_cb:
        nav.append(InlineKeyboardButton("← Prev month", callback_data=prev_month_cb))
    if next_month_cb:
        nav.append(InlineKeyboardButton("Next month →", callback_data=next_month_cb))
    if nav:
        rows.append(nav)

    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows), month_label


def _next_month(year, month):
    return (year, month + 1) if month < 12 else (year + 1, 1)


def _prev_month(year, month):
    return (year, month - 1) if month > 1 else (year - 1, 12)


def _kb_text_input(back_cb, skip=False):
    rows = []
    if skip:
        rows.append([InlineKeyboardButton("⏭ Skip", callback_data=SKIP_CB)])
    rows += _cancel_row(back_cb)
    return InlineKeyboardMarkup(rows)


# ── Event list display ────────────────────────────────────────────────────────

def _event_block(e: dict) -> str:
    lines = [
        f"📌 {e['title']}",
        f"📅 {e['event_date']}",
    ]
    if e.get("event_time"):
        lines.append(f"🕐 {e['event_time']}")
    lines.append(f"📍 {e['location']}")
    if e.get("description"):
        lines.append(f"📝 {e['description']}")
    return "\n".join(lines)


def _events_view(lang: str, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    events = db.get_all_special_events()
    is_admin = _is_admin(user_id)
    menu_btn = [[InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data="menu")]]

    if not events:
        empty_rows = []
        if is_admin:
            empty_rows.append([InlineKeyboardButton(get_text(lang, "ev_add_btn"), callback_data="ev_add")])
        empty_rows += menu_btn
        return get_text(lang, "events_empty"), InlineKeyboardMarkup(empty_rows)

    text = get_text(lang, "events_title") + "\n"
    rows = []

    for e in events:
        text += f"\n            \n{_event_block(e)}\n"

    if is_admin:
        rows.append([InlineKeyboardButton(get_text(lang, "ev_add_btn"), callback_data="ev_add")])
        rows.append([InlineKeyboardButton(get_text(lang, "ev_edit_btn"), callback_data="ev_edit_list")])
        rows.append([InlineKeyboardButton(get_text(lang, "ev_del_btn"), callback_data="ev_del_list")])

    rows += menu_btn
    return text, InlineKeyboardMarkup(rows)


async def events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text, kb = _events_view(_lang(context), update.effective_user.id)
    await query.edit_message_text(text, reply_markup=kb)


# ── Delete event ──────────────────────────────────────────────────────────────

async def ev_delask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang  = _lang(context)
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True); return
    await query.answer()
    event_id = int(query.data.split(":")[1])
    events   = db.get_all_special_events()
    ev       = next((e for e in events if e["id"] == event_id), None)
    if not ev:
        await query.answer("Event not found", show_alert=True); return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, delete", callback_data=f"ev_delconfirm:{event_id}"),
        InlineKeyboardButton("❌ No",          callback_data="events"),
    ]])
    await query.edit_message_text(
        get_text(lang, "ev_confirm_del") + "\n\n" + _event_block(ev),
        reply_markup=kb,
    )


async def ev_delconfirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True); return
    await query.answer()
    event_id = int(query.data.split(":")[1])
    db.delete_special_event(event_id)
    lang = _lang(context)
    text, kb = _events_view(lang, update.effective_user.id)
    await query.edit_message_text(text, reply_markup=kb)


# ── Edit event ────────────────────────────────────────────────────────────────

async def ev_edit_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang  = _lang(context)
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True)
        return ConversationHandler.END
    await query.answer()

    events = db.get_all_special_events()
    if not events:
        await query.answer("No events to edit", show_alert=True)
        return ConversationHandler.END

    rows = [[InlineKeyboardButton(
        f"🎉 {e['title']} ({e['event_date']})",
        callback_data=f"ev_edit:{e['id']}"
    )] for e in events]
    rows.append([InlineKeyboardButton("← Back", callback_data="events")])

    await query.edit_message_text(
        get_text(lang, "ev_choose_edit"),
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SE_MENU


async def ev_del_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang  = _lang(context)
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True)
        return ConversationHandler.END
    await query.answer()

    events = db.get_all_special_events()
    if not events:
        await query.answer("No events to delete", show_alert=True)
        return ConversationHandler.END

    rows = [[InlineKeyboardButton(
        f"🎉 {e['title']} ({e['event_date']})",
        callback_data=f"ev_delask:{e['id']}"
    )] for e in events]
    rows.append([InlineKeyboardButton("← Back", callback_data="events")])

    await query.edit_message_text(
        get_text(lang, "ev_choose_del"),
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return ConversationHandler.END


async def ev_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    lang  = _lang(context)
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True); return SE_MENU
    await query.answer()
    event_id = int(query.data.split(":")[1])
    context.user_data["ev_edit_id"] = event_id
    context.user_data["ev_msg_id"]  = query.message.message_id

    events = db.get_all_special_events()
    ev     = next((e for e in events if e["id"] == event_id), None)
    if not ev:
        await query.answer("Event not found", show_alert=True)
        return ConversationHandler.END

    context.user_data["ev_edit_data"] = dict(ev)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "ev_field_date"),  callback_data="eve_field:date")],
        [InlineKeyboardButton(get_text(lang, "ev_field_title"), callback_data="eve_field:title")],
        [InlineKeyboardButton(get_text(lang, "ev_field_loc"),   callback_data="eve_field:location")],
        [InlineKeyboardButton(get_text(lang, "ev_field_desc"),  callback_data="eve_field:desc")],
        [InlineKeyboardButton("← Back", callback_data="events")],
    ])
    await query.edit_message_text(
        get_text(lang, "ev_edit_menu") + "\n\n" + _event_block(ev),
        reply_markup=kb,
    )
    return SE_MENU


async def eve_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    field = query.data.split(":")[1]
    context.user_data["ev_edit_field"] = field
    ev    = context.user_data.get("ev_edit_data", {})

    if field == "date":
        await query.edit_message_text(
            f"📅 Current date: {ev.get('event_date','')}\n\nStep 1 — Choose month:",
            reply_markup=_kb_month(lang, cb_prefix="eve_month", back_cb="eve_back_menu"),
        )
        return SE_DATE_MONTH

    labels = {"title": "📌 Title", "location": "📍 Location", "desc": "📝 Description"}
    current = ev.get({"title":"title","location":"location","desc":"description"}[field], "")
    kb = _kb_text_input(back_cb="eve_back_menu", skip=(field=="desc"))
    await query.edit_message_text(
        f"Current {labels[field]}: {current}\n\nEnter new value:",
        reply_markup=kb,
    )
    return SE_TEXT


async def eve_back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    ev = context.user_data.get("ev_edit_data", {})
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "ev_field_date"),  callback_data="eve_field:date")],
        [InlineKeyboardButton(get_text(lang, "ev_field_title"), callback_data="eve_field:title")],
        [InlineKeyboardButton(get_text(lang, "ev_field_loc"),   callback_data="eve_field:location")],
        [InlineKeyboardButton(get_text(lang, "ev_field_desc"),  callback_data="eve_field:desc")],
        [InlineKeyboardButton("← Back", callback_data="events")],
    ])
    await query.edit_message_text(
        get_text(lang, "ev_edit_menu") + "\n\n" + _event_block(ev),
        reply_markup=kb,
    )
    return SE_MENU


async def eve_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_year"]  = year
    context.user_data["ev_month"] = month
    kb, month_label = _kb_day(year, month, lang, "eve_start_day", "eve_back_menu")
    await query.edit_message_text(
        f"📅 {month_label}\n\nChoose START day:",
        reply_markup=kb,
    )
    return SE_DATE_START


async def eve_start_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    start = query.data.split(":")[1]
    context.user_data["ev_date_start"] = start
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    context.user_data["ev_end_year"]  = year
    context.user_data["ev_end_month"] = month
    from datetime import date as _date
    ny, nm = _next_month(year, month)
    kb, month_label = _kb_day(year, month, lang, "eve_end_day", "eve_back_start_day",
                               min_date=_date.fromisoformat(start),
                               next_month_cb=f"eve_end_nav:{ny}:{nm}")
    await query.edit_message_text(
        f"📅 {month_label}  ▶ Start: {start}\n\nChoose END day:",
        reply_markup=kb,
    )
    return SE_DATE_END


async def eve_end_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate months in edit-event end day picker."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_end_year"]  = year
    context.user_data["ev_end_month"] = month
    start = context.user_data["ev_date_start"]
    from datetime import date as _date
    ny, nm = _next_month(year, month)
    py, pm = _prev_month(year, month)
    start_year  = context.user_data["ev_year"]
    start_month = context.user_data["ev_month"]
    prev_cb = f"eve_end_nav:{py}:{pm}" if (year, month) > (start_year, start_month) else None
    kb, month_label = _kb_day(year, month, lang, "eve_end_day", "eve_back_start_day",
                               min_date=_date.fromisoformat(start),
                               next_month_cb=f"eve_end_nav:{ny}:{nm}",
                               prev_month_cb=prev_cb)
    await query.edit_message_text(
        f"📅 {month_label}  ▶ Start: {start}\n\nChoose END day:",
        reply_markup=kb,
    )
    return SE_DATE_END


async def eve_back_start_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    kb, month_label = _kb_day(year, month, lang, "eve_start_day", "eve_back_menu")
    await query.edit_message_text(f"📅 {month_label}\n\nChoose START day:", reply_markup=kb)
    return SE_DATE_START


async def eve_end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    end   = query.data.split(":")[1]
    start = context.user_data["ev_date_start"]
    if end < start:
        await query.answer("⚠️ End must be same or after start", show_alert=True)
        return SE_DATE_END

    date_range = start if start == end else f"{start} – {end}"
    event_id   = context.user_data["ev_edit_id"]
    db._ensure_special_events_table()
    with db._connect() as conn:
        conn.execute("UPDATE special_events SET event_date=? WHERE id=?", (date_range, event_id))
    context.user_data["ev_edit_data"]["event_date"] = date_range

    lang = _lang(context)
    text, kb = _events_view(lang, update.effective_user.id)
    await query.edit_message_text(text, reply_markup=kb)
    return ConversationHandler.END


async def eve_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field   = context.user_data.get("ev_edit_field")
    value   = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    event_id = context.user_data["ev_edit_id"]
    msg_id   = context.user_data.get("ev_msg_id")
    lang     = _lang(context)

    col_map = {"title": "title", "location": "location", "desc": "description"}
    col     = col_map.get(field)
    if col:
        db._ensure_special_events_table()
        with db._connect() as conn:
            conn.execute(f"UPDATE special_events SET {col}=? WHERE id=?", (value, event_id))
        context.user_data["ev_edit_data"][col] = value

    text, kb = _events_view(lang, update.effective_user.id)
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=msg_id,
            text=text, reply_markup=kb,
        )
    except Exception:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=kb)
    return ConversationHandler.END


async def eve_skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query    = update.callback_query
    await query.answer()
    event_id = context.user_data["ev_edit_id"]
    db._ensure_special_events_table()
    with db._connect() as conn:
        conn.execute("UPDATE special_events SET description='' WHERE id=?", (event_id,))
    context.user_data["ev_edit_data"]["description"] = ""
    lang = _lang(context)
    text, kb = _events_view(lang, update.effective_user.id)
    await query.edit_message_text(text, reply_markup=kb)
    return ConversationHandler.END


# ── Add event flow ────────────────────────────────────────────────────────────

async def ev_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("⛔ Admin only", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    lang = _lang(context)

    for key in [k for k in context.user_data if k.startswith("ev_")]:
        del context.user_data[key]

    context.user_data["ev_msg_id"] = query.message.message_id

    await query.edit_message_text(
        "📅 Step 1 — Choose month:",
        reply_markup=_kb_month_extended(lang),
    )
    return S_MONTH


async def addevent_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END

    lang = _lang(context)
    try:
        await update.message.delete()
    except Exception:
        pass

    for key in [k for k in context.user_data if k.startswith("ev_")]:
        del context.user_data[key]

    msg = await update.effective_chat.send_message(
        "📅 Step 1 — Choose month:",
        reply_markup=_kb_month_extended(lang),
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
    kb, month_label = _kb_day(year, month, lang, "ev_start_day", None)
    await query.edit_message_text(
        f"📅 {month_label}\n\nStep 2 — Choose START day:",
        reply_markup=kb,
    )
    return S_START_DAY


async def ev_pick_start_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    start = query.data.split(":")[1]
    context.user_data["ev_date_start"] = start
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    # Initialize end month same as start month
    context.user_data["ev_end_year"]  = year
    context.user_data["ev_end_month"] = month
    from datetime import date as _date
    ny, nm = _next_month(year, month)
    kb, month_label = _kb_day(year, month, lang, "ev_end_day", "ev_back_to_start",
                               min_date=_date.fromisoformat(start),
                               next_month_cb=f"ev_end_nav:{ny}:{nm}")
    await query.edit_message_text(
        f"📅 {month_label}  ▶ Start: {start}\n\nStep 3 — Choose END day:",
        reply_markup=kb,
    )
    return S_END_DAY


async def ev_end_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Navigate months in end day picker."""
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)
    context.user_data["ev_end_year"]  = year
    context.user_data["ev_end_month"] = month
    start = context.user_data["ev_date_start"]
    from datetime import date as _date
    ny, nm = _next_month(year, month)
    py, pm = _prev_month(year, month)
    # Don't go before start month
    start_year  = context.user_data["ev_year"]
    start_month = context.user_data["ev_month"]
    prev_cb = f"ev_end_nav:{py}:{pm}" if (year, month) > (start_year, start_month) else None
    kb, month_label = _kb_day(year, month, lang, "ev_end_day", "ev_back_to_start",
                               min_date=_date.fromisoformat(start),
                               next_month_cb=f"ev_end_nav:{ny}:{nm}",
                               prev_month_cb=prev_cb)
    await query.edit_message_text(
        f"📅 {month_label}  ▶ Start: {start}\n\nStep 3 — Choose END day:",
        reply_markup=kb,
    )
    return S_END_DAY


async def ev_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data["ev_year"]
    month = context.user_data["ev_month"]
    kb, month_label = _kb_day(year, month, lang, "ev_start_day", None)
    await query.edit_message_text(
        f"📅 {month_label}\n\nStep 2 — Choose START day:",
        reply_markup=kb,
    )
    return S_START_DAY


async def ev_pick_end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    end   = query.data.split(":")[1]
    start = context.user_data["ev_date_start"]
    if end < start:
        await query.answer("⚠️ End must be same or after start", show_alert=True)
        return S_END_DAY
    context.user_data["ev_date_end"] = end
    date_range = start if start == end else f"{start} – {end}"
    context.user_data["ev_date"] = date_range
    kb = _kb_text_input(back_cb="ev_back_to_end")
    await query.edit_message_text(
        f"📅 {date_range}\n\n✏️ Step 4 — Enter event title:",
        reply_markup=kb,
    )
    return S_TITLE


async def ev_back_to_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(context)
    year  = context.user_data.get("ev_end_year", context.user_data["ev_year"])
    month = context.user_data.get("ev_end_month", context.user_data["ev_month"])
    start = context.user_data["ev_date_start"]
    from datetime import date as _date
    ny, nm = _next_month(year, month)
    py, pm = _prev_month(year, month)
    start_year  = context.user_data["ev_year"]
    start_month = context.user_data["ev_month"]
    prev_cb = f"ev_end_nav:{py}:{pm}" if (year, month) > (start_year, start_month) else None
    kb, month_label = _kb_day(year, month, lang, "ev_end_day", "ev_back_to_start",
                               min_date=_date.fromisoformat(start),
                               next_month_cb=f"ev_end_nav:{ny}:{nm}",
                               prev_month_cb=prev_cb)
    await query.edit_message_text(
        f"📅 {month_label}  ▶ Start: {start}\n\nStep 3 — Choose END day:",
        reply_markup=kb,
    )
    return S_END_DAY


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
    kb   = _kb_text_input(back_cb="ev_back_to_end", skip=True)
    text = f"📅 {date_range}\n📌 {title}\n\n✏️ Step 5 — Enter description (or skip):"
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=msg_id, text=text, reply_markup=kb)
    except Exception:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=kb)
        context.user_data["ev_msg_id"] = msg.message_id
    return S_DESC


async def ev_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_range = context.user_data["ev_date"]
    kb = _kb_text_input(back_cb="ev_back_to_end")
    await query.edit_message_text(
        f"📅 {date_range}\n\n✏️ Step 4 — Enter event title:",
        reply_markup=kb,
    )
    return S_TITLE


async def ev_enter_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ev_desc"] = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    return await _show_location_step(update.effective_chat.id, context)


async def ev_skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["ev_desc"] = ""
    return await _show_location_step(query.message.chat_id, context)


async def _show_location_step(chat_id, context):
    date_range = context.user_data["ev_date"]
    title      = context.user_data["ev_title"]
    msg_id     = context.user_data.get("ev_msg_id")
    kb   = _kb_text_input(back_cb="ev_back_to_desc")
    text = f"📅 {date_range}\n📌 {title}\n\n📍 Step 6 — Enter location:"
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb)
    except Exception:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
        context.user_data["ev_msg_id"] = msg.message_id
    return S_LOCATION


async def ev_back_to_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_range = context.user_data["ev_date"]
    title      = context.user_data["ev_title"]
    kb = _kb_text_input(back_cb="ev_back_to_title", skip=True)
    await query.edit_message_text(
        f"📅 {date_range}\n📌 {title}\n\n✏️ Step 5 — Enter description (or skip):",
        reply_markup=kb,
    )
    return S_DESC


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
        f"✅ Confirm new event:\n\n📌 {title}\n📅 {date_range}\n📍 {location}"
        + (f"\n📝 {desc}" if desc else "")
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save",   callback_data="ev_save"),
        InlineKeyboardButton("✖ Cancel", callback_data=CANCEL_CB),
    ]])
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=msg_id,
            text=preview, reply_markup=kb)
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=preview, reply_markup=kb)
    context.user_data["ev_ready"] = True
    return S_CONFIRM


async def ev_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang    = _lang(context)
    user_id = update.effective_user.id
    chat_id = query.message.chat_id
    msg_id  = query.message.message_id

    event_id = db.create_special_event(
        title       = context.user_data["ev_title"],
        event_date  = context.user_data["ev_date"],
        event_time  = "",
        location    = context.user_data["ev_location"],
        description = context.user_data.get("ev_desc", ""),
    )
    logger.info("Special event created id=%d", event_id)

    context.user_data.clear()
    context.user_data["lang"] = lang

    await query.edit_message_text(get_text(lang, "ev_saved"))

    async def _finish():
        import asyncio as _a
        await _a.sleep(2)
        try:
            await query.get_bot().delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
        try:
            text, kb = _events_view(lang, user_id)
            await query.get_bot().send_message(chat_id=chat_id, text=text, reply_markup=kb)
        except Exception:
            pass

    asyncio.ensure_future(_finish())
    return ConversationHandler.END


async def ev_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(context)
    context.user_data.clear()
    context.user_data["lang"] = lang

    if update.callback_query:
        await update.callback_query.answer()
        try:
            text, kb = _events_view(lang, update.effective_user.id)
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass
    else:
        try:
            await update.message.delete()
        except Exception:
            pass
    return ConversationHandler.END


async def ev_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return None


async def delevents_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only."); return
    try:
        await update.message.delete()
    except Exception:
        pass
    lang = _lang(context)
    text, kb = _events_view(lang, update.effective_user.id)
    await update.effective_chat.send_message(text, reply_markup=kb)


# ── Registration ──────────────────────────────────────────────────────────────

def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(events_callback, pattern="^events$"))
    application.add_handler(CallbackQueryHandler(ev_delask,     pattern=r"^ev_delask:\d+$"))
    application.add_handler(CallbackQueryHandler(ev_delconfirm, pattern=r"^ev_delconfirm:\d+$"))
    application.add_handler(CallbackQueryHandler(ev_del_list,   pattern="^ev_del_list$"))
    application.add_handler(CallbackQueryHandler(ev_edit_list,  pattern="^ev_edit_list$"))

    edit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ev_edit,      pattern=r"^ev_edit:\d+$"),
            CallbackQueryHandler(ev_edit_list, pattern="^ev_edit_list$"),
        ],
        states={
            SE_MENU: [
                CallbackQueryHandler(eve_field,       pattern=r"^eve_field:\w+$"),
                CallbackQueryHandler(ev_edit,         pattern=r"^ev_edit:\d+$"),
                CallbackQueryHandler(events_callback, pattern="^events$"),
            ],
            SE_DATE_MONTH: [
                CallbackQueryHandler(eve_month,     pattern=r"^eve_month:\d+:\d+$"),
                CallbackQueryHandler(eve_back_menu, pattern="^eve_back_menu$"),
            ],
            SE_DATE_START: [
                CallbackQueryHandler(eve_start_day,  pattern=r"^eve_start_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(eve_back_menu,  pattern="^eve_back_menu$"),
                CallbackQueryHandler(ev_noop,        pattern=f"^{NOOP_CB}$"),
            ],
            SE_DATE_END: [
                CallbackQueryHandler(eve_end_day,     pattern=r"^eve_end_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(eve_end_nav,     pattern=r"^eve_end_nav:\d+:\d+$"),
                CallbackQueryHandler(eve_back_start_day, pattern="^eve_back_start_day$"),
                CallbackQueryHandler(ev_noop,         pattern=f"^{NOOP_CB}$"),
            ],
            SE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, eve_text),
                CallbackQueryHandler(eve_skip_desc, pattern=f"^{SKIP_CB}$"),
                CallbackQueryHandler(eve_back_menu, pattern="^eve_back_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(events_callback, pattern="^events$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
    application.add_handler(edit_conv)

    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("addevent", addevent_start),
            CallbackQueryHandler(ev_add_callback, pattern="^ev_add$"),
        ],
        states={
            S_MONTH: [
                CallbackQueryHandler(ev_pick_month, pattern=r"^ev_month:\d+:\d+$"),
                CallbackQueryHandler(ev_cancel,     pattern=f"^{CANCEL_CB}$"),
            ],
            S_START_DAY: [
                CallbackQueryHandler(ev_pick_start_day, pattern=r"^ev_start_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_noop,           pattern=f"^{NOOP_CB}$"),
                CallbackQueryHandler(ev_cancel,         pattern=f"^{CANCEL_CB}$"),
            ],
            S_END_DAY: [
                CallbackQueryHandler(ev_pick_end_day, pattern=r"^ev_end_day:\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(ev_end_nav,      pattern=r"^ev_end_nav:\d+:\d+$"),
                CallbackQueryHandler(ev_back_to_start, pattern="^ev_back_to_start$"),
                CallbackQueryHandler(ev_noop,          pattern=f"^{NOOP_CB}$"),
                CallbackQueryHandler(ev_cancel,        pattern=f"^{CANCEL_CB}$"),
            ],
            S_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_title),
                CallbackQueryHandler(ev_back_to_end, pattern="^ev_back_to_end$"),
                CallbackQueryHandler(ev_cancel,      pattern=f"^{CANCEL_CB}$"),
            ],
            S_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_desc),
                CallbackQueryHandler(ev_skip_desc,   pattern=f"^{SKIP_CB}$"),
                CallbackQueryHandler(ev_back_to_title, pattern="^ev_back_to_title$"),
                CallbackQueryHandler(ev_cancel,      pattern=f"^{CANCEL_CB}$"),
            ],
            S_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_enter_location),
                CallbackQueryHandler(ev_back_to_desc, pattern="^ev_back_to_desc$"),
                CallbackQueryHandler(ev_cancel,       pattern=f"^{CANCEL_CB}$"),
            ],
            S_CONFIRM: [
                CallbackQueryHandler(ev_save,   pattern="^ev_save$"),
                CallbackQueryHandler(ev_cancel, pattern=f"^{CANCEL_CB}$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", ev_cancel),
            CallbackQueryHandler(ev_cancel,    pattern=f"^{CANCEL_CB}$"),
            CallbackQueryHandler(ev_edit_list, pattern="^ev_edit_list$"),
            CallbackQueryHandler(ev_del_list,  pattern="^ev_del_list$"),
            CallbackQueryHandler(ev_delask,    pattern=r"^ev_delask:\d+$"),
            CallbackQueryHandler(events_callback, pattern="^events$"),
        ],
        per_message=False,
        allow_reentry=True,
    )
    application.add_handler(add_conv)
    application.add_handler(CommandHandler("delevents", delevents_start))