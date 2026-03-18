"""
scheduler/reminders.py
-----------------------
Runs every minute. Sends reminders for upcoming bookings.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

import database as db
from config import REMINDER_MINUTES_BEFORE, GROUP_CHAT_ID
from translations import get_text

logger = logging.getLogger(__name__)


def _get_all_user_langs() -> dict:
    """Fetch all user langs in a single DB query."""
    try:
        with db._connect() as conn:
            rows = conn.execute("SELECT user_id, lang FROM users").fetchall()
        return {row["user_id"]: row["lang"] for row in rows}
    except Exception:
        return {}


async def _send_reminders(bot: Bot) -> None:
    now    = datetime.utcnow()
    target = now + timedelta(minutes=REMINDER_MINUTES_BEFORE)

    window_start = now.strftime("%Y-%m-%dT%H:%M")
    window_end   = (target + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")

    bookings = db.get_upcoming_bookings_needing_reminder(window_start, window_end)
    if not bookings:
        return  # Nothing to do — exit immediately

    # Single DB query for ALL user langs
    user_langs = _get_all_user_langs()

    for b in bookings:
        import datetime as _dt
        day_name = _dt.date.fromisoformat(b.date).strftime("%A, %b %d")

        # ── 1. Personal reminder to the booking owner ─────────────────────
        owner_lang   = user_langs.get(b.user_id, "en")
        personal_msg = (
            "⏰ Reminder — your booking starts in "
            + str(REMINDER_MINUTES_BEFORE)
            + " minutes!\n\n"
            + "📋 " + b.title + "\n"
            + "📅 " + b.date + "\n"
            + "🕐 " + b.start_time + " – " + b.end_time + "\n"
            + "👤 @" + b.username
        )
        try:
            await bot.send_message(chat_id=b.user_id, text=personal_msg)
            db.mark_reminder_sent(b.id)
            logger.info("Reminder sent: booking id=%d → user_id=%d", b.id, b.user_id)
        except TelegramError as exc:
            logger.warning("Personal reminder failed user_id=%d: %s", b.user_id, exc)
            continue

        # ── 2. Heads-up to ALL other users ────────────────────────────────
        all_user_ids = list(user_langs.keys())

        for uid in all_user_ids:
            if uid == b.user_id:
                continue
            user_lang   = user_langs.get(uid, "en")
            headsup_msg = (
                "⏰ Office in " + str(REMINDER_MINUTES_BEFORE) + " min\n\n"
                + get_text(user_lang, "group_notification",
                           day=day_name,
                           start=b.start_time,
                           end=b.end_time,
                           title=b.title,
                           user=b.username)
            )
            try:
                await bot.send_message(
                    chat_id      = uid,
                    text         = headsup_msg,
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            get_text(user_lang, "btn_dismiss"),
                            callback_data="notif_dismiss"
                        )
                    ]]),
                )
            except TelegramError as exc:
                logger.warning("Heads-up failed user_id=%d: %s", uid, exc)

        # ── 3. Group chat ──────────────────────────────────────────────────
        if GROUP_CHAT_ID:
            try:
                await bot.send_message(
                    chat_id = GROUP_CHAT_ID,
                    text    = (
                        "⏰ Office in " + str(REMINDER_MINUTES_BEFORE) + " min\n\n"
                        + get_text("en", "group_notification",
                                   day=day_name,
                                   start=b.start_time,
                                   end=b.end_time,
                                   title=b.title,
                                   user=b.username)
                    ),
                )
            except TelegramError as exc:
                logger.warning("Group chat reminder failed: %s", exc)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _send_reminders,
        trigger          = "interval",
        minutes          = 1,
        args             = [bot],
        id               = "reminder_job",
        replace_existing = True,
    )
    scheduler.start()
    logger.info(
        "Reminder scheduler started (fires %d min before each booking)",
        REMINDER_MINUTES_BEFORE,
    )
    return scheduler
