"""
bot.py
------
Application entry point.

Responsibilities:
  1. Initialise the database.
  2. Build the Telegram Application.
  3. Register all handlers.
  4. Start the reminder scheduler.
  5. Run the bot (polling or webhook depending on environment).
"""

import logging
import os

from telegram.ext import Application, MessageHandler, filters

import database
from config import BOT_TOKEN
from handlers import start, booking, schedule, mybookings, recurring, events
from scheduler.reminders import start_scheduler
from scheduler.log_bot import log_start, log_error
from scheduler.update_notify import send_update_notifications

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format  = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level   = logging.INFO,
)
logger = logging.getLogger(__name__)


# In-memory cache of registered user IDs — avoids DB hit on every update
_registered_users: set = set()

async def _track_user(update, context) -> None:
    """Register new users only. Uses in-memory cache to avoid DB reads."""
    user = update.effective_user
    if not user or user.is_bot:
        return
    if user.id in _registered_users:
        return  # Already known — skip DB entirely
    username = user.username or user.first_name or str(user.id)
    existing = database.get_user_lang(user.id)
    if existing is None:
        database.upsert_user(user.id, username, "en")
    else:
        # Restore lang from DB into user_data if missing
        if not context.user_data.get("lang"):
            context.user_data["lang"] = existing
    _registered_users.add(user.id)


def build_application() -> Application:
    """Wire everything together and return the Application."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Track every user automatically before any handler runs
    from telegram.ext import TypeHandler
    from telegram import Update as TGUpdate
    app.add_handler(TypeHandler(TGUpdate, _track_user), group=-1)

    # Register handlers (order matters — more specific first)
    events.register(app)        # Special events (registered first — simple callbacks)
    booking.register(app)       # ConversationHandler for booking flow
    recurring.register(app)     # Recurring bookings (/recurring command)
    mybookings.register(app)    # ConversationHandler for edit, simple handlers for list/cancel
    schedule.register(app)      # Schedule & free-time
    start.register(app)         # /start + menu + help (catch-all last)

    # Auto-delete any text message sent outside of a conversation flow
    # Uses group=1 so ConversationHandlers (group=0) always get priority
    async def _auto_delete(update, context):
        try:
            await update.message.delete()
        except Exception:
            pass

    # Update notification dismiss handler
    async def _update_notify_dismiss(update, context):
        query = update.callback_query
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass

    from telegram.ext import CallbackQueryHandler as _CQH
    app.add_handler(_CQH(_update_notify_dismiss, pattern="^update_notify_dismiss$"))

    from telegram.ext import MessageHandler as _MH, filters as _f

    # Auto-delete unknown commands (e.g. /something not registered)
    async def _auto_delete_command(update, context):
        try:
            await update.message.delete()
        except Exception:
            pass

    app.add_handler(_MH(_f.TEXT & ~_f.COMMAND, _auto_delete), group=1)
    app.add_handler(_MH(_f.COMMAND, _auto_delete_command), group=1)

    return app


def main() -> None:
    # 1. Prepare database
    database.init_db()

    # 2. Build application
    app = build_application()

    # 3. Start reminder scheduler
    start_scheduler(app.bot)

    # 4. Log bot startup to Telegram channel
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(log_start(app.bot))
    except Exception:
        pass

    # 4b. Send update notifications if UPDATE_NOTIFY=1
    try:
        asyncio.get_event_loop().run_until_complete(send_update_notifications(app.bot))
    except Exception as e:
        logger.warning("Update notify error: %s", e)

    # 5. Global error handler — sends all unhandled errors to log channel
    async def _error_handler(update, context) -> None:
        from telegram.error import Conflict, NetworkError
        # Ignore Conflict errors — expected during Railway restarts
        if isinstance(context.error, (Conflict, NetworkError)):
            logger.warning("Ignored expected error: %s", context.error)
            return
        await log_error(
            context.bot,
            f"Unhandled error (user: {update.effective_user.username if update and update.effective_user else 'unknown'})",
            context.error,
        )
        logger.error("Unhandled error", exc_info=context.error)

    app.add_error_handler(_error_handler)

    # 6. Delete any existing webhook and run polling
    import asyncio, time

    async def _delete_webhook():
        await app.bot.delete_webhook(drop_pending_updates=True)

    try:
        asyncio.get_event_loop().run_until_complete(_delete_webhook())
        logger.info("Webhook deleted, waiting 5s before polling…")
    except Exception as e:
        logger.warning("Could not delete webhook: %s", e)

    time.sleep(5)
    logger.info("Starting polling…")
    app.run_polling(
        drop_pending_updates = True,
        allowed_updates      = ["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
