"""
scheduler/log_bot.py
---------------------
Sends important bot events and errors to a Telegram log channel.

Usage anywhere in the code:
    from scheduler.log_bot import log_event, log_error

    await log_event(context.bot, "User @areg made a booking")
    await log_error(context.bot, "Database error", error)
"""

import logging
import os
import traceback

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Read from environment — set LOG_CHAT_ID in Railway variables
LOG_CHAT_ID: int | None = None
_raw = os.getenv("LOG_CHAT_ID", "")
if _raw.lstrip("-").isdigit():
    LOG_CHAT_ID = int(_raw)


async def log_event(bot: Bot, message: str) -> None:
    """Send an informational event to the log channel."""
    if not LOG_CHAT_ID:
        return
    try:
        await bot.send_message(
            chat_id    = LOG_CHAT_ID,
            text       = f"ℹ️ {message}",
            parse_mode = "Markdown",
        )
    except TelegramError as e:
        logger.warning("log_event failed: %s", e)


async def log_error(bot: Bot, context_msg: str, error: Exception = None) -> None:
    """Send an error to the log channel with traceback."""
    if not LOG_CHAT_ID:
        return
    tb = ""
    if error:
        tb = "\n```\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__))[-800:] + "\n```"

    text = f"🔴 *ERROR*\n{context_msg}{tb}"
    try:
        await bot.send_message(
            chat_id    = LOG_CHAT_ID,
            text       = text,
            parse_mode = "Markdown",
        )
    except TelegramError as e:
        logger.warning("log_error failed: %s", e)


async def log_booking(bot: Bot, username: str, title: str, date: str, start: str, end: str) -> None:
    """Send a booking confirmation event to the log channel."""
    if not LOG_CHAT_ID:
        return
    text = (
        f"📅 *New booking*\n"
        f"👤 @{username}\n"
        f"📋 {title}\n"
        f"🗓 {date}  {start} – {end}"
    )
    try:
        await bot.send_message(
            chat_id    = LOG_CHAT_ID,
            text       = text,
            parse_mode = "Markdown",
        )
    except TelegramError as e:
        logger.warning("log_booking failed: %s", e)


async def log_start(bot: Bot) -> None:
    """Send a message when the bot starts up."""
    if not LOG_CHAT_ID:
        return
    import datetime
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    try:
        await bot.send_message(
            chat_id    = LOG_CHAT_ID,
            text       = f"✅ *Bot started*\n🕐 {now}",
            parse_mode = "Markdown",
        )
    except TelegramError as e:
        logger.warning("log_start failed: %s", e)
