"""
scheduler/reminders.py
-----------------------
Runs every minute.
- Sends reminders 1 hour before each booking (Asia/Yerevan timezone)
- Personal reminder to booking owner
- Heads-up to all other users with dismiss button
- Auto-deletes reminder messages after 15 minutes
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

import database as db
from config import REMINDER_MINUTES_BEFORE, GROUP_CHAT_ID
from translations import get_text, WEEKDAY_NAMES, MONTH_SHORT

logger = logging.getLogger(__name__)

# Module-level dict to track pending notification message IDs per user
# {user_id: [msg_id, msg_id, ...]}
PENDING_NOTIFS: dict[int, list[int]] = {}

YEREVAN = ZoneInfo("Asia/Yerevan")


def _get_all_user_langs() -> dict:
    """Fetch all user langs in a single DB query."""
    try:
        with db._connect() as conn:
            rows = conn.execute("SELECT user_id, lang FROM users").fetchall()
        return {row["user_id"]: row["lang"] for row in rows}
    except Exception:
        return {}


def _day_label(date_str: str, lang: str) -> str:
    """Return translated day label e.g. 'Երкушабти, 18 Мрт'"""
    from datetime import date
    d = date.fromisoformat(date_str)
    day_name  = WEEKDAY_NAMES.get(lang, WEEKDAY_NAMES["en"])[d.weekday()]
    month_name = MONTH_SHORT.get(lang, MONTH_SHORT["en"])[d.month - 1]
    return f"{day_name}, {d.day} {month_name}"


async def _auto_delete(bot: Bot, chat_id: int, message_id: int, delay_seconds: int) -> None:
    """Delete a message after delay_seconds. Silent — ignores errors."""
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _send_reminders(bot: Bot) -> None:
    # ── Current time in Yerevan ───────────────────────────────────────────
    now_yerevan    = datetime.now(YEREVAN)
    target_yerevan = now_yerevan + timedelta(minutes=REMINDER_MINUTES_BEFORE)

    # Window: bookings starting between now+REMINDER and now+REMINDER+1min
    window_start = target_yerevan.strftime("%Y-%m-%dT%H:%M")
    window_end   = (target_yerevan + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")

    bookings = db.get_upcoming_bookings_needing_reminder(window_start, window_end)
    if not bookings:
        return

    user_langs = _get_all_user_langs()

    for b in bookings:

        # ── 1. Personal reminder to booking owner ────────────────────────
        owner_lang = user_langs.get(b.user_id, "en")
        day_label  = _day_label(b.date, owner_lang)

        personal_msg = (
            f"⏰ {get_text(owner_lang, 'reminder_title', minutes=REMINDER_MINUTES_BEFORE)}\n\n"
            f"📋 {b.title}\n"
            f"📅 {day_label}\n"
            f"🕐 {b.start_time} – {b.end_time}\n"
            f"👤 {b.display_user}"
        )

        dismiss_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                get_text(owner_lang, "btn_dismiss"),
                callback_data="notif_dismiss"
            )
        ]])

        try:
            sent = await bot.send_message(
                chat_id      = b.user_id,
                text         = personal_msg,
                reply_markup = dismiss_kb,
            )
            db.mark_reminder_sent(b.id)
            logger.info("Reminder sent: booking id=%d → user_id=%d", b.id, b.user_id)
            # Auto-delete after 15 minutes
            asyncio.ensure_future(_auto_delete(bot, b.user_id, sent.message_id, 5 * 60))
        except TelegramError as exc:
            logger.warning("Personal reminder failed user_id=%d: %s", b.user_id, exc)
            continue

        # ── 2. Heads-up to ALL other users ───────────────────────────────
        for uid, user_lang in user_langs.items():
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

            headsup_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    get_text(user_lang, "btn_dismiss"),
                    callback_data="notif_dismiss"
                )
            ]])

            try:
                sent = await bot.send_message(
                    chat_id      = uid,
                    text         = headsup_msg,
                    reply_markup = headsup_kb,
                )
                # Auto-delete after 15 minutes
                asyncio.ensure_future(_auto_delete(bot, uid, sent.message_id, 5 * 60))
                PENDING_NOTIFS.setdefault(uid, []).append(sent.message_id)
            except TelegramError as exc:
                logger.warning("Heads-up failed user_id=%d: %s", uid, exc)

        # ── 3. Group chat ─────────────────────────────────────────────────
        if GROUP_CHAT_ID:
            try:
                day_label_en = _day_label(b.date, "en")
                sent = await bot.send_message(
                    chat_id = GROUP_CHAT_ID,
                    text    = (
                        f"📢 Office in {REMINDER_MINUTES_BEFORE} min\n\n"
                        f"📅 {day_label_en}\n"
                        f"🕐 {b.start_time} – {b.end_time}\n"
                        f"📋 {b.title}\n"
                        f"👤 {b.display_user}"
                    ),
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            get_text("en", "btn_dismiss"),
                            callback_data="notif_dismiss"
                        )
                    ]]),
                )
                asyncio.ensure_future(_auto_delete(bot, GROUP_CHAT_ID, sent.message_id, 5 * 60))
            except TelegramError as exc:
                logger.warning("Group chat reminder failed: %s", exc)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=YEREVAN)
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
        "Reminder scheduler started (Asia/Yerevan, fires %d min before each booking)",
        REMINDER_MINUTES_BEFORE,
    )
    return scheduler
