"""
scheduler/reminders.py
-----------------------
APScheduler job that runs every minute and sends reminder messages
to users whose booking starts in ~REMINDER_MINUTES_BEFORE minutes.

The job uses a separate reminder_sent table so it never fires twice
for the same booking.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError

import database as db
from config import REMINDER_MINUTES_BEFORE

logger = logging.getLogger(__name__)


async def _send_reminders(bot: Bot) -> None:
    """Check for bookings that need a reminder and send them."""
    now    = datetime.utcnow()
    target = now + timedelta(minutes=REMINDER_MINUTES_BEFORE)

    # Look for bookings whose start is in the next [now, target+1min] window
    window_start = now.strftime("%Y-%m-%dT%H:%M")
    window_end   = (target + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")

    bookings = db.get_upcoming_bookings_needing_reminder(window_start, window_end)

    for b in bookings:
        text = (
            f"⏰ *Reminder* — your booking starts in ~{REMINDER_MINUTES_BEFORE} minutes!\n\n"
            f"{b.full_text()}"
        )
        try:
            await bot.send_message(
                chat_id    = b.user_id,
                text       = text,
                parse_mode = "Markdown",
            )
            db.mark_reminder_sent(b.id)
            logger.info("Reminder sent for booking id=%d to user_id=%d", b.id, b.user_id)
        except TelegramError as exc:
            logger.warning("Could not send reminder to user_id=%d: %s", b.user_id, exc)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create and start the scheduler. Returns the scheduler instance."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _send_reminders,
        trigger  = "interval",
        minutes  = 1,
        args     = [bot],
        id       = "reminder_job",
        replace_existing = True,
    )
    scheduler.start()
    logger.info("Reminder scheduler started (interval: 1 min)")
    return scheduler
