"""
scheduler/reminders.py
-----------------------
Runs every minute.
- Sends booking reminders 1 hour before each booking (Asia/Yerevan timezone)
- Sends special event reminders 24 hours before each event
- Personal reminder to booking owner
- Heads-up to all other users with dismiss button
- Auto-deletes reminder messages after 5 minutes
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

import database as db
from config import REMINDER_MINUTES_BEFORE, GROUP_CHAT_ID
from translations import get_text, WEEKDAY_NAMES, MONTH_SHORT

logger = logging.getLogger(__name__)

YEREVAN = ZoneInfo("Asia/Yerevan")

# Module-level dict to track pending notification message IDs per user
PENDING_NOTIFS: dict[int, list[int]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_all_user_langs(club_id: str = "") -> dict:
    try:
        with db._connect() as conn:
            if club_id:
                rows = conn.execute(
                    "SELECT user_id, lang FROM users WHERE club_id=?", (club_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT user_id, lang FROM users").fetchall()
        return {row["user_id"]: row["lang"] for row in rows}
    except Exception:
        return {}


def _day_label(date_str: str, lang: str) -> str:
    d = date.fromisoformat(date_str)
    day_name   = WEEKDAY_NAMES.get(lang, WEEKDAY_NAMES["en"])[d.weekday()]
    month_name = MONTH_SHORT.get(lang, MONTH_SHORT["en"])[d.month - 1]
    return f"{day_name}, {d.day} {month_name}"


async def _auto_delete(bot: Bot, chat_id: int, message_id: int, delay_seconds: int) -> None:
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _send_with_dismiss(bot: Bot, chat_id: int, text: str, lang: str) -> None:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text(lang, "btn_dismiss"), callback_data="notif_dismiss")
    ]])
    try:
        sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
        asyncio.ensure_future(_auto_delete(bot, chat_id, sent.message_id, 5 * 60))
        PENDING_NOTIFS.setdefault(chat_id, []).append(sent.message_id)
        try:
            db.save_notification(chat_id, chat_id, sent.message_id)
        except Exception:
            pass
    except TelegramError as exc:
        logger.warning("Notification failed chat_id=%d: %s", chat_id, exc)


# ── Booking reminders ─────────────────────────────────────────────────────────

async def _send_reminders(bot: Bot) -> None:
    now_yerevan    = datetime.now(YEREVAN)
    target_yerevan = now_yerevan + timedelta(minutes=REMINDER_MINUTES_BEFORE)

    window_start = target_yerevan.strftime("%Y-%m-%dT%H:%M")
    window_end   = (target_yerevan + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")

    bookings = db.get_upcoming_bookings_needing_reminder(window_start, window_end)
    if not bookings:
        return

    for b in bookings:
        club_user_langs = _get_all_user_langs(club_id=b.club_id)
        owner_lang = club_user_langs.get(b.user_id, "en")
        day_label  = _day_label(b.date, owner_lang)

        personal_msg = (
            f"⏰ {get_text(owner_lang, 'reminder_title', minutes=REMINDER_MINUTES_BEFORE)}\n\n"
            f"📋 {b.title}\n"
            f"📅 {day_label}\n"
            f"🕐 {b.start_time} – {b.end_time}\n"
            f"👤 {b.display_user}"
        )

        try:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text(owner_lang, "btn_dismiss"), callback_data="notif_dismiss")
            ]])
            sent = await bot.send_message(chat_id=b.user_id, text=personal_msg, reply_markup=kb)
            db.mark_reminder_sent(b.id)
            logger.info("Reminder sent: booking id=%d → user_id=%d", b.id, b.user_id)
            asyncio.ensure_future(_auto_delete(bot, b.user_id, sent.message_id, 5 * 60))
            PENDING_NOTIFS.setdefault(b.user_id, []).append(sent.message_id)
            try:
                db.save_notification(b.user_id, b.user_id, sent.message_id)
            except Exception:
                pass
        except TelegramError as exc:
            logger.warning("Personal reminder failed user_id=%d: %s", b.user_id, exc)
            continue

        for uid, user_lang in club_user_langs.items():
            if uid == b.user_id:
                continue
            day_label_u = _day_label(b.date, user_lang)
            headsup_msg = (
                f"📢 {get_text(user_lang, 'reminder_headsup', minutes=REMINDER_MINUTES_BEFORE)}\n\n"
                f"📅 {day_label_u}\n"
                f"🕐 {b.start_time} – {b.end_time}\n"
                f"📋 {b.title}\n"
                f"👤 {b.display_user}"
            )
            await _send_with_dismiss(bot, uid, headsup_msg, user_lang)

        if GROUP_CHAT_ID:
            day_label_en = _day_label(b.date, "en")
            group_msg = (
                f"📢 Office in {REMINDER_MINUTES_BEFORE} min\n\n"
                f"📅 {day_label_en}\n"
                f"🕐 {b.start_time} – {b.end_time}\n"
                f"📋 {b.title}\n"
                f"👤 {b.display_user}"
            )
            await _send_with_dismiss(bot, GROUP_CHAT_ID, group_msg, "en")


# ── Special event reminders ───────────────────────────────────────────────────

def _get_event_start_date(event_date: str) -> str:
    return event_date.replace(" ", "").split("–")[0].strip()


def _event_reminder_sent(event_id: int) -> bool:
    try:
        with db._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM event_reminder_sent WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None
    except Exception:
        return False


def _mark_event_reminder_sent(event_id: int) -> None:
    try:
        with db._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO event_reminder_sent (event_id, sent_at) VALUES (?, ?)",
                (event_id, datetime.now(YEREVAN).isoformat())
            )
    except Exception as e:
        logger.warning("Could not mark event reminder sent: %s", e)


async def _send_event_reminders(bot: Bot) -> None:
    """Send 24-hour-before reminders for special events."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    try:
        events = db.get_all_special_events()
    except Exception:
        return

    events_tomorrow = [
        ev for ev in events
        if _get_event_start_date(ev["event_date"]) == tomorrow
    ]

    if not events_tomorrow:
        return

    for ev in events_tomorrow:
        if _event_reminder_sent(ev["id"]):
            continue

        logger.info("Sending 24h reminder for special event id=%d: %s", ev["id"], ev["title"])
        ev_club_id = ev.get("club_id", "")
        ev_user_langs = _get_all_user_langs(club_id=ev_club_id)

        for uid, lang in ev_user_langs.items():
            msg = (
                f"🎉 {get_text(lang, 'event_reminder_title')}\n\n"
                f"📌 {ev['title']}\n"
                f"📅 {ev['event_date']}"
            )
            if ev.get("location"):
                msg += f"\n📍 {ev['location']}"
            if ev.get("description"):
                msg += f"\n📝 {ev['description']}"

            await _send_with_dismiss(bot, uid, msg, lang)

        _mark_event_reminder_sent(ev["id"])


# ── Scheduler setup ───────────────────────────────────────────────────────────

async def _run_all_reminders(bot: Bot) -> None:
    await _send_reminders(bot)
    await _send_event_reminders(bot)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=YEREVAN)
    scheduler.add_job(
        _run_all_reminders,
        trigger          = "interval",
        minutes          = 1,
        args             = [bot],
        id               = "_send_reminders",
        replace_existing = True,
    )
    scheduler.start()
    logger.info("Reminder scheduler started (Asia/Yerevan, fires 60 min before each booking)")
    return scheduler
