"""
handlers/start.py
-----------------
/start command, welcome screen, language picker, and main menu.

Flow for new users:
    /start  ->  Welcome screen  ->  [Continue]  ->  Language picker  ->  Main menu

Flow for returning users:
    /start  ->  Main menu directly (language already saved)

HOW TO EDIT THE WELCOME TEXT
------------------------------
Find the WELCOME_TEXT variable below and replace it with your own text.
Use *bold* and _italic_ for formatting.
The text will be shown in Armenian to all new users before they pick a language.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from translations import get_text, DEFAULT_LANG

MENU_CALLBACK = "menu"

# ===========================================================================
# WELCOME TEXT — edit this to write your own description
# ===========================================================================
# This message is shown ONCE to every new user when they first open the bot.
# Supports Telegram Markdown: *bold*, _italic_, `code`
# Replace the text below with your own words in Armenian.
# ===========================================================================

WELCOME_TEXT = (
    "🏢 *Center Club*\n\n"
    "Բари галуст!\n\n"
    "✏️ _Айстег гри ко нкарагрутюнт айеренов — инчу е стеղцвел айс бот у "
    "инч кароголутюннер ка ноутвор оgтакорцогнери хамар:_\n\n"
    "Оринак:\n"
    "«Айс ботн у ствел мер чентеракlубум офисы арагагравар пронируму "
    "хамар: Ка горцацу ев дицел азат жамер аканатесел нарарел ев челаркел "
    "кнджаинтерут'юннерен:»"
)

# ===========================================================================


def _kb_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️  Շарунакел", callback_data="welcome_continue")]
    ])


def _kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧  English",  callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺  Русский",  callback_data="lang:ru")],
        [InlineKeyboardButton("🇦🇲  Հայերեն", callback_data="lang:hy")],
    ])


def _main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    t = lambda key: get_text(lang, key)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_book_office"),   callback_data="book")],
        [InlineKeyboardButton(t("btn_view_schedule"), callback_data="schedule")],
        [InlineKeyboardButton(t("btn_my_bookings"),   callback_data="mybookings")],
        [InlineKeyboardButton(t("btn_help"),          callback_data="help")],
        [InlineKeyboardButton(t("btn_language"),      callback_data="choose_lang")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data.get("lang")
    if not lang:
        # New user: show welcome screen
        await update.message.reply_text(
            WELCOME_TEXT,
            parse_mode="Markdown",
            reply_markup=_kb_welcome(),
        )
    else:
        # Returning user: go straight to menu
        await update.message.reply_text(
            get_text(lang, "start_message"),
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(lang),
        )


async def welcome_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped Continue — show language picker."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🌐 Ընтреk лезун / Выберите язык / Choose language",
        reply_markup=_kb_language(),
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
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    await query.edit_message_text(
        get_text(lang, "start_message"),
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(lang),
    )


async def choose_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await query.edit_message_text(
        get_text(lang, "help_text"),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data=MENU_CALLBACK)
        ]]),
    )


def register(application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(welcome_continue,     pattern="^welcome_continue$"))
    application.add_handler(CallbackQueryHandler(set_language,         pattern=r"^lang:(en|ru|hy)$"))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))