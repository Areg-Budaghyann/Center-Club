"""
handlers/start.py
-----------------
/start command, language picker, and main menu.
The main menu buttons are now localised via get_text().
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from translations import get_text, DEFAULT_LANG
from handlers.booking import _kb_language

MENU_CALLBACK = "menu"


def _main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    """Build the main menu in the user's language."""
    t = lambda key: get_text(lang, key)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("book_office"),              callback_data="book")],
        [InlineKeyboardButton("📊 View schedule",          callback_data="schedule")],
        [InlineKeyboardButton("📌 My bookings",            callback_data="mybookings")],
        [InlineKeyboardButton("🟢 Free time",              callback_data="freetime")],
        [InlineKeyboardButton("ℹ️ Help",                    callback_data="help")],
        [InlineKeyboardButton("🌐 Language",               callback_data="choose_lang")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — show language picker if no language set, else show menu."""
    lang = context.user_data.get("lang")

    if not lang:
        # First time: ask for language
        await update.message.reply_text(
            "🌐 Choose language / Выберите язык / Ընտրեք լեզուն",
            reply_markup=_kb_language(),
        )
    else:
        await update.message.reply_text(
            get_text(lang, "start_message"),
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(lang),
        )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the '← Menu' button."""
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    await query.edit_message_text(
        get_text(lang, "start_message"),
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(lang),
    )


async def choose_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-show the language picker when user taps 🌐 Language."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🌐 Choose language / Выберите язык / Ընտրեք լեզուն",
        reply_markup=_kb_language(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    text = (
        "ℹ️ *Help*\n\n"
        "*📅 Book office* — reserve a time slot step by step.\n"
        "*📊 View schedule* — see weekly or monthly bookings.\n"
        "*📌 My bookings* — view, edit, or cancel your reservations.\n"
        "*🟢 Free time* — check what hours are available.\n\n"
        "Office hours: 10:00 – 23:00\n"
        "Max booking: 6 hours"
    )
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text(lang, "menu_button"), callback_data=MENU_CALLBACK)
        ]]),
    )


def register(application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))
