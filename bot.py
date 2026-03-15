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

from telegram.ext import Application

import database
from config import BOT_TOKEN
from handlers import start, booking, schedule, mybookings, recurring
from scheduler.reminders import start_scheduler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format  = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level   = logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    """Wire everything together and return the Application."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers (order matters — more specific first)
    booking.register(app)       # ConversationHandler for booking flow
    recurring.register(app)     # Recurring bookings (/recurring command)
    mybookings.register(app)    # ConversationHandler for edit, simple handlers for list/cancel
    schedule.register(app)      # Schedule & free-time
    start.register(app)         # /start + menu + help (catch-all last)

    return app


def main() -> None:
    # 1. Prepare database
    database.init_db()

    # 2. Build application
    app = build_application()

    # 3. Start reminder scheduler
    start_scheduler(app.bot)

    # 4. Determine run mode
    webhook_url = os.getenv("WEBHOOK_URL")  # e.g. https://myapp.railway.app

    if webhook_url:
        # ── Webhook mode (production) ──────────────────────────────────────
        port = int(os.getenv("PORT", "8443"))
        logger.info("Starting webhook on port %d", port)
        app.run_webhook(
            listen       = "0.0.0.0",
            port         = port,
            webhook_url  = f"{webhook_url}/{BOT_TOKEN}",
            url_path     = BOT_TOKEN,
        )
    else:
        # ── Polling mode (local development) ──────────────────────────────
        logger.info("Starting polling…")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()