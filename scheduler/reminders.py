"""
scheduler/reminders.py
-----------------------
Two jobs run every minute:

1. PERSONAL REMINDER — sent to the booking owner 60 min before their event.
   Uses the owner's language from the users table.

2. GROUP REMINDER — sent to ALL other users 60 min before any booking starts,
   so everyone knows the office will be in use.
   Each user gets the message in their own language.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError

import database as db
from config import REMINDER_MINUTES_BEFORE, GROUP_CHAT_ID
from translations import get_text

logger = logging.getLogger(__name__)


def _user_lang(user_id: int) -> str:
    """Fetch the stored language for a user, defaulting to 'en'."""
    try:
        with db._connect() as conn:
            row = conn.execute(
                "SELECT lang FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row["lang"] if row else "en"
    except Exception:
        return "en"


async def _send_reminders(bot: Bot) -> None:
    """
    Called every minute.
    Finds bookings starting in ~REMINDER_MINUTES_BEFORE minutes and:
      - Sends a personal reminder to the booking owner
      - Sends a heads-up notification to ALL other users
    """
    now    = datetime.utcnow()
    target = now + timedelta(minutes=REMINDER_MINUTES_BEFORE)

    window_start = now.strftime("%Y-%m-%dT%H:%M")
    window_end   = (target + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")

    bookings = db.get_upcoming_bookings_needing_reminder(window_start, window_end)

    for b in bookings:

        # ── 1. Personal reminder to the booking owner ─────────────────────
        owner_lang = _user_lang(b.user_id)
        personal_text = (
            f"⏰ *{get_text(owner_lang, 'btn_my_bookings')}* — "
            f"{REMINDER_MINUTES_BEFORE} min\n\n"
            f"{b.full_text()}"
        )
        try:
            await bot.send_message(
                chat_id    = b.user_id,
                text       = personal_text,
                parse_mode = "Markdown",
            )
            db.mark_reminder_sent(b.id)
            logger.info("Personal reminder sent: booking id=%d → user_id=%d", b.id, b.user_id)
        except TelegramError as exc:
            logger.warning("Personal reminder failed user_id=%d: %s", b.user_id, exc)
            continue  # still try group notifications below

        # ── 2. Heads-up to ALL other users ────────────────────────────────
        import datetime as _dt
        day_name = _dt.date.fromisoformat(b.date).strftime("%A, %b %d")
        all_user_ids = db.get_all_user_ids()

        for uid in all_user_ids:
            if uid == b.user_id:
                continue  # owner already got personal reminder above

            user_lang = _user_lang(uid)
            headsup_text = (
                f"⏰ *Office in {REMINDER_MINUTES_BEFORE} min*\n\n"
                + get_text(user_lang, "group_notification",
                           day=day_name,
                           start=b.start_time,
                           end=b.end_time,
                           title=b.title,
                           user=b.username)
            )
            try:
                await bot.send_message(
                    chat_id    = uid,
                    text       = headsup_text,
                    parse_mode = "Markdown",
                )
            except TelegramError as exc:
                logger.warning("Heads-up failed user_id=%d: %s", uid, exc)

        # ── 3. Also send to group chat if configured ───────────────────────
        if GROUP_CHAT_ID:
            try:
                await bot.send_message(
                    chat_id    = GROUP_CHAT_ID,
                    text       = (
                        f"⏰ *Office in {REMINDER_MINUTES_BEFORE} min*\n\n"
                        + get_text("en", "group_notification",
                                   day=day_name,
                                   start=b.start_time,
                                   end=b.end_time,
                                   title=b.title,
                                   user=b.username)
                    ),
                    parse_mode = "Markdown",
                )
            except TelegramError as exc:
                logger.warning("Group chat reminder failed: %s", exc)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create and start the APScheduler. Returns the scheduler instance."""
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
    logger.info("Reminder scheduler started (checks every 1 min, fires %d min before booking)", REMINDER_MINUTES_BEFORE)
    return scheduler