"""
handlers/start.py
-----------------
/start command with multi-club authentication.

New user flow:
    /start → club picker (17 clubs, 2/row) → password entry →
    language picker → main menu

Returning user flow:
    /start → check user_data["club_id"] → check DB →
    restore lang → show main menu directly
"""

import database
from config import CLUBS, get_club_name, verify_club_password, STATE_PICK_CLUB, STATE_ENTER_PASSWORD
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters,
)
from translations import get_text, DEFAULT_LANG, HELP_TEXTS

MENU_CALLBACK = "menu"


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _kb_clubs() -> InlineKeyboardMarkup:
    clubs = list(CLUBS.items())
    rows = []
    for i in range(0, len(clubs), 2):
        row = []
        for club_id, info in clubs[i:i+2]:
            row.append(InlineKeyboardButton(info["name"], callback_data=f"club:{club_id}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


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
        [InlineKeyboardButton(t("btn_events"),        callback_data="events")],
        [InlineKeyboardButton(t("btn_help"),          callback_data="help")],
        [InlineKeyboardButton(t("btn_language"),      callback_data="choose_lang")],
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cleanup_notifications(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete pending notification messages for the user."""
    menu_msg_id = context.bot_data.get("menu_msgs", {}).get(user_id)
    pending = context.bot_data.get("pending_notifs", {})
    import asyncio
    async def _do():
        for msg_id in pending.pop(user_id, []):
            if msg_id == menu_msg_id:
                continue
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                pass
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
    asyncio.ensure_future(_do())


async def _show_main_menu(
    chat_id: int,
    lang: str,
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    msg_id_to_edit: int = None,
) -> None:
    text = get_text(lang, "start_message")
    kb   = _main_menu_keyboard(lang)
    if msg_id_to_edit:
        try:
            msg = await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id_to_edit,
                text=text, reply_markup=kb,
            )
            context.bot_data.setdefault("menu_msgs", {})[user_id] = msg.message_id
            return
        except Exception:
            pass
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    context.bot_data.setdefault("menu_msgs", {})[user_id] = msg.message_id


# ── /start entry ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id if update.effective_user else None

    # Delete /start message
    try:
        await update.message.delete()
    except Exception:
        pass

    if user_id:
        _cleanup_notifications(user_id, context)

    # Check if already authenticated
    club_id = context.user_data.get("club_id")
    if not club_id and user_id:
        club_id = database.get_user_club(user_id)
        if club_id:
            context.user_data["club_id"] = club_id

    if club_id:
        lang = context.user_data.get("lang")
        if not lang and user_id:
            lang = database.get_user_lang(user_id) or "en"
            context.user_data["lang"] = lang
        lang = lang or "en"
        # Delete old menu message if it exists, then send a fresh one
        old_menu_id = context.bot_data.get("menu_msgs", {}).get(user_id)
        if old_menu_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=old_menu_id
                )
            except Exception:
                pass
            context.bot_data.get("menu_msgs", {}).pop(user_id, None)
        await _show_main_menu(update.effective_chat.id, lang, user_id, context)
        return ConversationHandler.END

    # Not authenticated — show club picker
    lang = context.user_data.get("lang", "en")
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=get_text(lang, "choose_club"),
        reply_markup=_kb_clubs(),
    )
    context.user_data["club_auth_msg_id"] = msg.message_id
    return STATE_PICK_CLUB


# ── Club selection ────────────────────────────────────────────────────────────

async def pick_club(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    club_id = query.data.split(":")[1]
    context.user_data["pending_club_id"] = club_id
    context.user_data["club_auth_msg_id"] = query.message.message_id

    lang = context.user_data.get("lang", "en")
    club_name = get_club_name(club_id)

    await query.edit_message_text(
        get_text(lang, "enter_password", club=club_name),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("← Back", callback_data="back_to_clubs"),
        ]]),
        parse_mode="Markdown",
    )
    return STATE_ENTER_PASSWORD


async def back_to_clubs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")
    context.user_data.pop("pending_club_id", None)
    await query.edit_message_text(
        get_text(lang, "choose_club"),
        reply_markup=_kb_clubs(),
    )
    return STATE_PICK_CLUB


# ── Password entry ────────────────────────────────────────────────────────────

async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    user_id  = update.effective_user.id
    chat_id  = update.effective_chat.id

    # Delete password message immediately for security
    try:
        await update.message.delete()
    except Exception:
        pass

    club_id = context.user_data.get("pending_club_id")
    lang    = context.user_data.get("lang", "en")
    msg_id  = context.user_data.get("club_auth_msg_id")

    if not club_id:
        await context.bot.send_message(chat_id=chat_id,
            text=get_text(lang, "choose_club"), reply_markup=_kb_clubs())
        return STATE_PICK_CLUB

    if not verify_club_password(club_id, password):
        # Wrong password — stay in password state
        club_name = get_club_name(club_id)
        error_text = (
            get_text(lang, "wrong_password") + "\n\n"
            + get_text(lang, "enter_password", club=club_name)
        )
        back_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("← Back", callback_data="back_to_clubs"),
        ]])
        if msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id,
                    text=error_text, reply_markup=back_kb,
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return STATE_ENTER_PASSWORD

    # Correct password — save club_id
    context.user_data["club_id"] = club_id
    context.user_data.pop("pending_club_id", None)
    username = update.effective_user.username or update.effective_user.first_name or str(user_id)
    existing_lang = context.user_data.get("lang")

    # Save to DB
    database.upsert_user(user_id, username, existing_lang or "en", club_id)

    if not existing_lang:
        # Show language picker
        lang_text = get_text("en", "choose_language")
        if msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id,
                    text=lang_text, reply_markup=_kb_language(),
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=chat_id, text=lang_text, reply_markup=_kb_language())
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=lang_text, reply_markup=_kb_language())
        return ConversationHandler.END
    else:
        # Language already set — go to main menu
        await _show_main_menu(chat_id, existing_lang, user_id, context, msg_id_to_edit=msg_id)
        return ConversationHandler.END


# ── Language selection ────────────────────────────────────────────────────────

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    context.user_data["lang"] = lang

    user = update.effective_user
    if user:
        username = user.username or user.first_name or str(user.id)
        club_id  = context.user_data.get("club_id", "")
        database.upsert_user(user.id, username, lang, club_id)

    user_id = update.effective_user.id if update.effective_user else None
    msg = await query.edit_message_text(
        get_text(lang, "start_message"),
        reply_markup=_main_menu_keyboard(lang),
    )
    if user_id:
        context.bot_data.setdefault("menu_msgs", {})[user_id] = msg.message_id


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
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", DEFAULT_LANG)
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
    await application.bot.delete_my_commands(scope=None)


def register(application: Application) -> None:
    # Auth conversation (club selection + password)
    auth_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            STATE_PICK_CLUB: [
                CallbackQueryHandler(pick_club,      pattern=r"^club:"),
            ],
            STATE_ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_password),
                CallbackQueryHandler(back_to_clubs,  pattern="^back_to_clubs$"),
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_message=False,
        allow_reentry=True,
    )
    application.add_handler(auth_conv)

    application.add_handler(CallbackQueryHandler(set_language,         pattern=r"^lang:(en|ru|hy)$"))
    application.add_handler(CallbackQueryHandler(menu_callback,        pattern=f"^{MENU_CALLBACK}$"))
    application.add_handler(CallbackQueryHandler(choose_lang_callback, pattern="^choose_lang$"))
    application.add_handler(CallbackQueryHandler(help_callback,        pattern="^help$"))
