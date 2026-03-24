"""
handlers/start.py
-----------------
/start command, language picker, and main menu.

Flow for new users:    /start -> language picker -> main menu
Flow for returning:    /start -> main menu directly
"""

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from translations import get_text, DEFAULT_LANG, HELP_TEXTS

MENU_CALLBACK = "menu"

def _kb_language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧  English",  callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺  Русский",  callback_data="lang:ru")],
        [InlineKeyboardButton("🇦🇲  Հայerен",  callback_data="lang:hy")],
    ])


def _main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    t = lambda key: get_text(lang, key)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_book_office"),   callback_data="book")],
        [InlineKeyboardButton(t("btn_view_schedule"), callback_data="schedule")],
        [InlineKeyboardButton(t("btn_my_bookings"),   callback_data="mybookings")],
        [InlineKeyboardButton(t("btn_free_time"),     callback_data="freetime")],
        [InlineKeyboardButton(t("btn_events"), callback_data="events")],
        [InlineKeyboardButton(t("btn_help"),          callback_data="help")],
        [InlineKeyboardButton(t("btn_language"),      callback_data="choose_lang")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Delete the /start command message to keep chat clean
    try:
        await update.message.delete()
    except Exception:
        pass

    # Delete any pending notification/reminder messages for this user
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        menu_msg_id = context.bot_data.get("menu_msgs", {}).get(user_id)  # protect menu
        # From booking notifications (bot_data)
        pending = context.bot_data.get("pending_notifs", {})
        for msg_id in pending.pop(user_id, []):
            if msg_id == menu_msg_id:
                continue
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                pass
        # From reminders (module-level dict)
        try:
            from scheduler.reminders import PENDING_NOTIFS
            for msg_id in PENDING_NOTIFS.pop(user_id, []):
                if msg_id == menu_msg_id:
                    continue
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
                except Exception:
                    pass
        except Exception:
            pass

    lang = context.user_data.get("lang")
    # Restore lang from DB if user_data was cleared (e.g. after bot restart)
    if not lang and update.effective_user:
        import database as _db
        lang = _db.get_user_lang(update.effective_user.id)
        if lang:
            context.user_data["lang"] = lang
    if not lang:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_text("en", "choose_language"),
            reply_markup=_kb_language(),
        )
    else:
        menu_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_text(lang, "start_message"),
            reply_markup=_main_menu_keyboard(lang),
        )
        # Store menu message ID so other handlers never accidentally delete it
        # Store in bot_data keyed by user_id — survives ConversationHandler.END
        context.bot_data.setdefault("menu_msgs", {})[update.effective_user.id] = menu_msg.message_id


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang
    # Save language choice to DB so it persists across restarts
    import database as _db
    user = update.effective_user
    if user:
        username = user.username or user.first_name or str(user.id)
        _db.upsert_user(user.id, username, lang)
    msg = await query.edit_message_text(
        get_text(lang, "start_message"),
        reply_markup=_main_menu_keyboard(lang),
    )
    if update.effective_user:
        context.bot_data.setdefault("menu_msgs", {})[update.effective_user.id] = msg.message_id


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
    msg = await query.edit_message_text(
        get_text(lang, "start_message"),
        reply_markup=_main_menu_keyboard(lang),
    )
    if update.effective_user:
        context.bot_data.setdefault("menu_msgs", {})[update.effective_user.id] = msg.message_id


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
    # Hide all other commands from the menu
    await application.bot.delete_my_commands(scope=None)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language,         pattern=r"^lang:(en|ru|hy)$"))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))
