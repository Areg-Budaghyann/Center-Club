"""
scheduler/update_notify.py
---------------------------
One-time update notification sent to all users on deployment.

- Cleans old pending notification messages
- Sends update notification about Special Events feature
- Auto-deletes notification after 5 minutes
- Button dismisses immediately

Set env var UPDATE_NOTIFY=1 to trigger on next startup.
After sending, set it back to 0 (or remove it).
"""

import asyncio
import logging
import os

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

import database as db
from scheduler.reminders import PENDING_NOTIFS

logger = logging.getLogger(__name__)

UPDATE_TEXTS = {
    "en": (
        "🚀 Bot updated!\n\n"
        "📌 New section: 🎉 Special Events\n\n"
        "You can now view upcoming special events from the main menu.\n"
        "• 👤 All users — can view events\n"
        "• 🔐 Admins only — can add, edit, delete events"
    ),
    "ru": (
        "🚀 Бот обновлён!\n\n"
        "📌 Новый раздел: 🎉 Специальные события\n\n"
        "Теперь вы можете просматривать предстоящие события из главного меню.\n"
        "• 👤 Все пользователи — могут просматривать события\n"
        "• 🔐 Только администраторы — могут добавлять, редактировать, удалять события"
    ),
    "hy": (
        "🚀 Բոտը թարմացվել է!\n\n"
        "📌 Նոր բաժին՝ 🎉 Հատուկ միջոցառումներ\n\n"
        "Այժմ կարող եք տեսնել առաջիկա միջոցառումները գլխավոր մենյուից։\n"
        "• 👤 Բոլոր օգտատերերը — կարող են դիտել միջոցառումները\n"
        "• 🔐 Միայն ադմինները — կարող են ավելացնել, փոփոխել և ջնջել միջոցառումները"
),
}

DISMISS_TEXTS = {
    "en": "👌 Got it",
    "ru": "👌 Окей, понятно",
    "hy": "👌 Շատ լավ, հասկացա",
}


async def _safe_delete(bot: Bot, chat_id: int, msg_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


async def _auto_delete_after(bot: Bot, chat_id: int, msg_id: int, delay: int = 300) -> None:
    await asyncio.sleep(delay)
    await _safe_delete(bot, chat_id, msg_id)


async def send_update_notifications(bot: Bot) -> None:
    """
    Called once on startup when UPDATE_NOTIFY=1.
    1. Cleans all pending notification messages for all users
    2. Sends update notification to each user
    3. Schedules auto-delete after 5 minutes
    """
    if os.getenv("UPDATE_NOTIFY", "0") != "1":
        return

    logger.info("UPDATE_NOTIFY=1 — sending update notifications to all users")

    # Get all users and their langs
    try:
        with db._connect() as conn:
            rows = conn.execute("SELECT user_id, lang FROM users").fetchall()
        users = [(row["user_id"], row["lang"] or "en") for row in rows]
    except Exception as e:
        logger.error("Failed to get users for update notify: %s", e)
        return

    if not users:
        logger.info("No users to notify")
        return

    # Clean all pending notifications for all users first
    for user_id, _ in users:
        for msg_id in PENDING_NOTIFS.pop(user_id, []):
            await _safe_delete(bot, user_id, msg_id)

    # Send update notification to each user
    sent_count = 0
    for user_id, lang in users:
        text    = UPDATE_TEXTS.get(lang, UPDATE_TEXTS["en"])
        dismiss = DISMISS_TEXTS.get(lang, DISMISS_TEXTS["en"])
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(dismiss, callback_data="update_notify_dismiss")
        ]])
        try:
            msg = await bot.send_message(
                chat_id      = user_id,
                text         = text,
                reply_markup = kb,
            )
            # Auto-delete after 5 minutes
            asyncio.ensure_future(_auto_delete_after(bot, user_id, msg.message_id))
            sent_count += 1
        except TelegramError as e:
            logger.warning("Update notify failed for user_id=%d: %s", user_id, e)

    logger.info("Update notification sent to %d/%d users", sent_count, len(users))
