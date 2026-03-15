"""
handlers/start.py
-----------------
/start command, language picker, and main menu.
All texts come from translations.py.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from translations import get_text, DEFAULT_LANG

MENU_CALLBACK = "menu"


def _kb_language() -> InlineKeyboardMarkup:
    """Language selection keyboard — always shown in all 3 languages."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧  English",  callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺  Русский",  callback_data="lang:ru")],
        [InlineKeyboardButton("🇦🇲  Հայերեն", callback_data="lang:hy")],
    ])


def _main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    """Build the main menu using translated button labels."""
    t = lambda key: get_text(lang, key)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_book_office"),    callback_data="book")],
        [InlineKeyboardButton(t("btn_view_schedule"),  callback_data="schedule")],
        [InlineKeyboardButton(t("btn_my_bookings"),    callback_data="mybookings")],
        [InlineKeyboardButton(t("btn_free_time"),      callback_data="freetime")],
        [InlineKeyboardButton(t("btn_help"),           callback_data="help")],
        [InlineKeyboardButton(t("btn_language"),       callback_data="choose_lang")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — show language picker if no language chosen yet, else show menu."""
    lang = context.user_data.get("lang")
    if not lang:
        await update.message.reply_text(
            get_text("en", "choose_language"),
            reply_markup=_kb_language(),
        )
    else:
        await update.message.reply_text(
            get_text(lang, "start_message"),
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(lang),
        )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store chosen language and show the main menu."""
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang
    await query.edit_message_text(
        get_text(lang, "start_message"),
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(lang),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the ← Menu button from any sub-screen."""
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
        get_text("en", "choose_language"),
        reply_markup=_kb_language(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    await query.edit_message_text(
        get_text(lang, "help_text"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data=MENU_CALLBACK)
        ]]),
    )


def register(application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language,         pattern=r"^lang:(en|ru|hy)$"))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))