"""
bot_reset_hook.py
------------------
PTB post-update hook that checks for admin-requested soft reset.
Registered as a TypeHandler in group=-2 (runs before everything).
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_reset_in_progress = False


async def check_reset_hook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if admin requested a soft reset and perform it if so."""
    global _reset_in_progress

    from scheduler.bot_state import reset_requested, clear_reset_flag, perform_soft_reset

    if not reset_requested() or _reset_in_progress:
        return

    _reset_in_progress = True
    try:
        logger.info("Admin reset requested — performing soft reset...")
        clear_reset_flag()  # Remove flag first to prevent double-trigger
        stats = await perform_soft_reset(context.application)
        logger.info("Soft reset complete: %s", stats)
    except Exception as e:
        logger.error("Soft reset failed: %s", e)
    finally:
        _reset_in_progress = False
