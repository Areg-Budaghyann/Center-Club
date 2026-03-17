"""
handlers/start.py
-----------------
/start command, language picker, and main menu.

Flow for new users:    /start -> language picker -> main menu
Flow for returning:    /start -> main menu directly
"""

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from translations import get_text, DEFAULT_LANG

MENU_CALLBACK = "menu"

# ── Help texts per language — exact text, no modifications ───────────────────
HELP_TEXTS = {
    "hy": (
        "📅 Ամրագրել ակումբը — քայլ առ քայլ ընտրել և ամրագրել ժամանակը։\n\n"
        "📊 Տեսնել ակումբի գրաֆիկը— տեսնել ամրագրումները շաբաթվա կամ ամսվա կտրվածքով:\n\n"
        "📌 Իմ ամրագրումները — տեսնել, փոփոխել կամ չեղարկել ձեր ամրագրումները։\n\n"
        "🟢 Ազատ ժամանակ — ստուգել, թե որ ժամերն են հասանելի։"
    ),
    "ru": (
        "📅 Забронировать клуб — пошагово выбрать и зарезервировать время.\n\n"
        "📊 Посмотреть расписание — увидеть бронирования на неделю или месяц.\n\n"
        "📌 Мои бронирования — просмотреть, изменить или отменить свои брони.\n\n"
        "🟢 Свободное время — проверить, какие часы доступны."
    ),
    "en": (
        "📅 Book club — reserve a time slot step by step.\n\n"
        "📊 View schedule — see weekly or monthly bookings.\n\n"
        "📌 My bookings — view, edit, or cancel your reservations.\n\n"
        "🟢 Free time — check what hours are available."
    ),
}


def _kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧  English",  callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺  Русский",  callback_data="lang:ru")],
        [InlineKeyboardButton("🇦🇲  Հայերեն",  callback_data="lang:hy")],
    ])


def _main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    t = lambda key: get_text(lang, key)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_book_office"),   callback_data="book")],
        [InlineKeyboardButton(t("btn_view_schedule"), callback_data="schedule")],
        [InlineKeyboardButton(t("btn_my_bookings"),   callback_data="mybookings")],
        [InlineKeyboardButton(t("btn_free_time"),     callback_data="freetime")],
        [InlineKeyboardButton(t("btn_help"),          callback_data="help")],
        [InlineKeyboardButton(t("btn_language"),      callback_data="choose_lang")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Delete the /start command message to keep chat clean
    try:
        await update.message.delete()
    except Exception:
        pass

    lang = context.user_data.get("lang")
    if not lang:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_text("en", "choose_language"),
            reply_markup=_kb_language(),
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_text(lang, "start_message"),
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(lang),
        )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        get_text("en", "choose_language"),
        reply_markup=_kb_language(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help — shows exact text in user's selected language."""
    query = update.callback_query
    await query.answer()

    # Language is stored in context.user_data["lang"] by set_language()
    # Defaults to "en" if not set
    lang = context.user_data.get("lang", DEFAULT_LANG)

    # Select exact help text for this language
    help_text = HELP_TEXTS.get(lang, HELP_TEXTS["en"])

    await query.edit_message_text(
        help_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text(lang, "btn_menu"), callback_data=MENU_CALLBACK)
        ]]),
    )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Open the bot"),
    ])


def register(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language,         pattern=r"^lang:(en|ru|hy)$"))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))
