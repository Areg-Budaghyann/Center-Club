"""
handlers/start.py
-----------------
/start command and the main menu.
All other flows are entered from here.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

MENU_CALLBACK = "menu"


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Book office",   callback_data="book")],
        [InlineKeyboardButton("📊 View schedule", callback_data="schedule")],
        [InlineKeyboardButton("📌 My bookings",   callback_data="mybookings")],
        [InlineKeyboardButton("🟢 Free time",     callback_data="freetime")],
        [InlineKeyboardButton("ℹ️ Help",           callback_data="help")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — show the main menu."""
    text = (
        "👋 *Office Booking Bot*\n\n"
        "Reserve a time slot in our shared office.\n"
        "What would you like to do?"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the '← Menu' button that appears on sub-screens."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "What would you like to do?",
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ *Help*\n\n"
        "*📅 Book office* — reserve a time slot step by step.\n"
        "*📊 View schedule* — see weekly or monthly bookings.\n"
        "*📌 My bookings* — view, edit, or cancel your reservations.\n"
        "*🟢 Free time* — check what hours are available today or another day.\n\n"
        "Office hours: 10:00 – 23:00\n"
        "Max booking: 6 hours"
    )
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("← Menu", callback_data=MENU_CALLBACK)]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)


# ── Registration helper ───────────────────────────────────────────────────────

def register(application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
