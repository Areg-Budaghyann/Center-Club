"""
translations.py
================
ALL user-facing texts for the Club Booking Bot live here.

HOW TO EDIT
-----------
1. Find the section you want to change (e.g. "MY BOOKINGS", "ERRORS", etc.)
2. Edit the text under the language you want ("en", "ru", "hy")
3. Save the file and restart the bot — changes take effect immediately.

VARIABLES IN TEXTS
------------------
Some texts contain placeholders like {title}, {date}, {user}.
Do NOT remove the curly braces or rename these — they are filled in
automatically by the bot at runtime.

HOW TO ADD A NEW LANGUAGE
--------------------------
1. Copy the entire "en" block
2. Paste it and rename "en" to your language code (e.g. "fr")
3. Translate all values
4. Add the language button in the LANGUAGE_PICKER section at the bottom

USAGE IN CODE
-------------
    from translations import T, get_text

    # Simple text:
    msg = get_text(lang, "start_message")

    # Text with variables:
    msg = get_text(lang, "booking_conflict", start="15:00", end="18:00",
                   title="Board Games", user="areg")
"""

# ===========================================================================
# MAIN TRANSLATION DICTIONARY
# ===========================================================================
# Structure:  T[language_code][text_key] = "text"
# ===========================================================================

T: dict[str, dict[str, str]] = {

    # -----------------------------------------------------------------------
    # ENGLISH
    # -----------------------------------------------------------------------
    "en": {

        # ── START & MAIN MENU ───────────────────────────────────────────────
        "start_message":         "Below you can find all the features available in this bot 📋\n\nIf you have any questions, press the “Help” button ℹ️\n\nPlan your time wisely ⏰✨",
        "choose_language":       "🌐 Choose language / Выберите язык / Ընտրեք լեզուն",
        "language_changed":      "✅ Language set to English.",

        # ── MAIN MENU BUTTONS ───────────────────────────────────────────────
        "btn_book_office":       "📅 Book club",
        "btn_view_schedule":     "📊 View schedule",
        "btn_my_bookings":       "📌 My bookings",
        "btn_free_time":         "🟢 Free time",
        "btn_help":              "ℹ️ Help",
        "btn_language":          "🌐 Language",

        # ── HELP ────────────────────────────────────────────────────────────
        "help_text":             (
            "ℹ️ *Help*\n\n"
            "*📅 Book club* — reserve a time slot step by step.\n"
            "*📊 View schedule* — see weekly or monthly bookings.\n"
            "*📌 My bookings* — view, edit, or cancel your reservations.\n"
            "*🟢 Free time* — check what hours are available.\n\n"
            "club hours: 10:00 – 23:00\n"
            "Max booking: 6 hours"
        ),

        # ── BOOKING FLOW ────────────────────────────────────────────────────
        "choose_month":          "📅Step 1 of 4 — Choose a month:",
        "choose_day":            "📅 *{month}* — choose a day:",
        "choose_time":           "📅 {date}\n\n🕐 Step 2 of 4 — Choose start time:",
        "choose_duration":       "📅 {date}  |  🕐 {hour}:00\n\n⏱ Step 3 of 4 — Choose duration:",
        "enter_title":           "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}h\n\n✏️ Step 4 of 4 — Enter event title:\n\n Type the name of your event (e.g. Board Games, Team Meeting)",
        "enter_title_again":     "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}h\n\n✏️ Step 4 of 4 — Enter event title:\n\n Type the name of your event",
        "confirm_preview":       "✅ Confirm your booking:\n\n📋 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}h)\n👤 {user}",
        "booking_confirmed":     "🎉 Booking confirmed!\n\n{details}",
        "booking_cancelled":     "Booking cancelled.",

        # ── BOOKING CONFLICT ────────────────────────────────────────────────
        "booking_conflict":      (
            "❌ Time slot already booked!\n\n"
            "This time overlaps with:\n\n"
            "🕐 {start} – {end}\n"
            "📋 {title}\n"
            "👤 {user}\n\n"
            "Please choose a different time."
        ),
        "slot_taken_alert":      "⛔ This hour is already booked.",
        "slot_taken_detail":     "🔒 Already booked!\n\n📋 {title}\n🕐 {start} – {end}\n👤 {user}",

        # ── GROUP NOTIFICATION ──────────────────────────────────────────────
        "group_notification":    "📢 New club booking\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 {title}\n👤 Organiser: {user}",

        # ── MY BOOKINGS ─────────────────────────────────────────────────────
        "my_bookings_title":     "📌 My bookings — tap one to manage it:",
        "my_bookings_empty":     "📌 My bookings\n\nYou have no upcoming bookings.",
        "booking_not_found":     "Booking not found.",
        "booking_deleted":       "✅ Booking cancelled.",
        "booking_delete_failed": "❌ Could not cancel: {reason}",
        "btn_delete_all":        "🗑 Delete all my bookings",
        "btn_delete_all_yes":    "✅ Yes, delete all",
        "delete_all_confirm":    "⚠️ Delete all bookings?\n\nThis will cancel all {count} upcoming bookings. This cannot be undone.",
        "delete_all_done":       "✅ Done. {count} booking(s) deleted.",


        # ── EDIT BOOKING ────────────────────────────────────────────────────
        "edit_title":            "✏️ Edit booking — what would you like to change?",
        "edit_pick_duration":    "Current duration: *{duration}h*\n\nPick new duration:",
        "edit_pick_start_time":  "Current start: *{start_time}*\n\nPick new start time:",
        "edit_pick_date":        "Current date: *{date}*\n\nPick new date:",
        "edit_pick_title":       "Current title: *{title}*\n\nType the new title:",
        "edit_updated":          "✅ Updated!\n\n{details}",
        "edit_title_updated":    "✅ Title updated!\n\n{details}",
        "edit_failed":           "❌ {reason}",
        "edit_cancelled":        "Edit cancelled.",
        "edit_unknown_action":   "Unknown action.",
        "edit_unexpected_input": "Unexpected input. Please use the buttons.",

        # ── BUTTONS — EDIT ──────────────────────────────────────────────────
        "btn_edit":              "✏️ Edit",
        "btn_delete":            "🗑 Cancel booking",
        "btn_edit_title":        "✏️ Title",
        "btn_edit_date":         "📅 Date",
        "btn_edit_start_time":   "🕐 Start time",
        "btn_edit_duration":     "⏱ Duration",
        "btn_my_bookings_back":  "← My bookings",

        # ── NAVIGATION BUTTONS ──────────────────────────────────────────────
        "btn_back":              "←  Back",
        "btn_cancel":            "✖  Cancel",
        "btn_confirm":           "✅  Confirm",
        "btn_menu":              "←  Menu",
        "btn_change_title":      "←  Change title",

        # ── SCHEDULE ────────────────────────────────────────────────────────
        "schedule_title":        "📊 View schedule — pick a period:",
        "btn_this_week":         "📅 This week",
        "btn_next_week":         "📅Next week",
        "btn_this_month":        "📆 This month",
        "btn_next_month":        "📆Next month",
        "no_bookings_this_month":"No bookings this month.",
        "no_bookings_day":       "📭 No bookings for this day.",

        # ── FREE TIME ───────────────────────────────────────────────────────
        "free_time_title":       "🟢 Free time — pick a day:",
        "free_slots_header":     "🟢 Free slots on {day}:\n",
        "no_free_slots":         "_No free time available._",

        # ── VALIDATION ERRORS ───────────────────────────────────────────────
        "title_empty":           "Please enter a title for your event.",
        "title_too_long":        "Title is too long ({length} chars). Max 80 characters — please shorten it.",
        "title_invalid":         "Invalid title (1–80 characters). Try again.",
        "past_day_alert":        "That day is already in the past.",
        "error_message":         "Something went wrong. Please try again.",
        "no_permission":         "⛔ You don't have permission to use this command.",
        "btn_dismiss":           "👌 OK, got you!",

        # ── RECURRING BOOKINGS ──────────────────────────────────────────────
        "recurring_intro":       (
            "📅 *Recurring booking*\n\n"
            "This will book every *{weekday}* from "
            "*{start}* to *{end}*.\n\n"
            "*Step 1 — Choose the START date:*\n"
            "_(Pick the month first)_"
        ),
        "recurring_pick_to":     "✅ Start date: *{from_date}*\n\n*Step 2 — Choose the END date:*\n_(Pick the month first)_",
        "recurring_pick_from_day": "📅 *{month}* — choose the START day:",
        "recurring_pick_to_day": "📅 *{month}* — choose the END day:",
        "recurring_enter_title": (
            "📅 *{from_date}* → *{to_date}*\n"
            "🗓 Every *{weekday}* · {start}–{end}\n\n"
            "✏️ *Enter the event title:*\n_(e.g. Weekly Meeting)_"
        ),
        "recurring_preview":     (
            "✅ *Confirm recurring booking:*\n\n"
            "📋 *{title}*\n"
            "🗓 Every {weekday}\n"
            "🕐 {start} – {end}\n"
            "📅 {from_date} → {to_date}\n"
            "🔢 *{count} bookings* will be created"
        ),
        "recurring_success":     "🎉 *{count} recurring bookings created!*\n",
        "recurring_skipped":     "\n⚠️ *{count} dates skipped* (already booked):",
        "recurring_cancelled":   "Recurring booking cancelled.",
        "recurring_title_invalid": "Please enter a valid title (1–80 chars).",
        "recurring_pick_from_month": "Choose the START month:",
        "recurring_pick_to_month":   "Choose the END month:",

        # ── Free time check ──────────────────────────────────────────────

        "free_label":    "🟢 Free:",
        "booked_label":  "🔒 Booked:",
        "no_free_label": "🔴 No free time this day.",

         # ── 1 hour reminder ──────────────────────────────────────────────
        "reminder_title":   "⏰ Your booking starts in {minutes} minutes!",
        "reminder_headsup": "⏰ Club booked in {minutes} minutes",  

    },
    # -----------------------------------------------------------------------
    # RUSSIAN
    # -----------------------------------------------------------------------
    "ru": {

        "start_message":         "Ниже представлены все возможности этого бота 📋\n\nЕсли у вас возникнут вопросы, нажмите кнопку «Помощь» ℹ️\n\nПланируйте своё время с умом ⏰✨",
        "choose_language":       "🌐 Choose language / Выберите язык / Ընտրեք լեզուն",
        "language_changed":      "✅ Язык изменён на Русский.",

        "btn_book_office":       "📅 Забронировать клуб",
        "btn_view_schedule":     "📊 Расписание",
        "btn_my_bookings":       "📌 Мои брони",
        "btn_free_time":         "🟢 Свободное время",
        "btn_help":              "ℹ️ Помощь",
        "btn_language":          "🌐 Язык",

        "help_text":             (
            "ℹ️ *Помощь*\n\n"
            "*📅 Забронировать клуб* — пошаговое бронирование.\n"
            "*📊 Расписание* — просмотр недельного или месячного расписания.\n"
            "*📌 Мои брони* — просмотр, редактирование или отмена броней.\n"
            "*🟢 Свободное время* — проверить доступные часы.\n\n"
            "Часы работы: 10:00 – 23:00\n"
            "Максимальная бронь: 6 часов"
        ),

        "choose_month":          "📅 Шаг 1 из 4 — Выберите месяц:",
        "choose_day":            "📅 *{month}* — выберите день:",
        "choose_time":           "📅 {date}\n\n🕐 Шаг 2 из 4 — Выберите время начала:",
        "choose_duration":       "📅 {date}  |  🕐 {hour}:00\n\n⏱ Шаг 3 из 4 — Выберите длительность:",
        "enter_title":           "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ч\n\n✏️ Шаг 4 из 4 — Введите название: \n\nНапример: Настольные игры, Встреча команды",
        "enter_title_again":     "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ч\n\n✏️ Шаг 4 из 4 — Введите название: \n\n_Введите название события_",
        "confirm_preview":       "✅ Подтвердите бронирование: \n\n📋 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}ч)\n👤 {user}",
        "booking_confirmed":     "🎉 Бронирование подтверждено!\n\n{details}",
        "booking_cancelled":     "Бронирование отменено.",

        "booking_conflict":      (
            "❌ Это время уже занято!\n\n"
            "Пересечение с:\n\n"
            "🕐 {start} – {end}\n"
            "📋 {title}\n"
            "👤 {user}\n\n"
            "Пожалуйста, выберите другое время."
        ),
        "slot_taken_alert":      "⛔ Этот час уже занят.",
        "slot_taken_detail":     "🔒 Уже занято!\n\n📋 {title}\n🕐 {start} – {end}\n👤 {user}",

        "group_notification":    "📢 Новое бронирование клуба\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 {title}\n👤 Организатор: {user}",

        "my_bookings_title":     "📌 Мои брони — нажмите для управления:",
        "my_bookings_empty":     "📌 Мои брони\n\nУ вас нет предстоящих броней.",
        "booking_not_found":     "Бронирование не найдено.",
        "booking_deleted":       "✅ Бронирование отменено.",
        "booking_delete_failed": "❌ Не удалось отменить: {reason}",
        "btn_delete_all":        "🗑 Удалить все мои брони",
        "btn_delete_all_yes":    "✅ Да, удалить все",
        "delete_all_confirm":    "⚠️ Удалить все брони?\n\nЭто отменит все {count} предстоящих броней. Отменить невозможно.",
        "delete_all_done":       "✅ Готово. Удалено {count} бронирований.",

        "edit_title":            "✏️ Редактировать бронь — что изменить?",
        "edit_pick_duration":    "Текущая длительность: *{duration}ч*\n\nВыберите новую:",
        "edit_pick_start_time":  "Текущее время: *{start_time}*\n\nВыберите новое:",
        "edit_pick_date":        "Текущая дата: *{date}*\n\nВыберите новую:",
        "edit_pick_title":       "Текущее название: *{title}*\n\nВведите новое:",
        "edit_updated":          "✅ Обновлено!\n\n{details}",
        "edit_title_updated":    "✅ Название обновлено!\n\n{details}",
        "edit_failed":           "❌ {reason}",
        "edit_cancelled":        "Редактирование отменено.",
        "edit_unknown_action":   "Неизвестное действие.",
        "edit_unexpected_input": "Неожиданный ввод. Используйте кнопки.",

        "btn_edit":              "✏️ Редактировать",
        "btn_delete":            "🗑 Отменить бронь",
        "btn_edit_title":        "✏️ Название",
        "btn_edit_date":         "📅 Дата",
        "btn_edit_start_time":   "🕐 Время начала",
        "btn_edit_duration":     "⏱ Длительность",
        "btn_my_bookings_back":  "← Мои брони",

        "btn_back":              "←  Назад",
        "btn_cancel":            "✖  Отмена",
        "btn_confirm":           "✅  Подтвердить",
        "btn_menu":              "←  Меню",
        "btn_change_title":      "←  Изменить название",

        "schedule_title":        "📊 Расписание — выберите период:",
        "btn_this_week":         "📅 Эта неделя",
        "btn_next_week":         "📅 Следующая неделя",
        "btn_this_month":        "📆 Этот месяц",
        "btn_next_month":        "📆 Следующий месяц",
        "no_bookings_this_month":"Броней в этом месяце нет.",
        "no_bookings_day":       "📭 На этот день броней нет.",

        "free_time_title":       "🟢 Свободное время — выберите день:",
        "free_slots_header":     "🟢 Свободные слоты {day}:\n",
        "no_free_slots":         "_Свободного времени нет._",

        "title_empty":           "Пожалуйста, введите название события.",
        "title_too_long":        "Название слишком длинное ({length} символов). Максимум 80.",
        "title_invalid":         "Недопустимое название (1–80 символов). Попробуйте снова.",
        "past_day_alert":        "Этот день уже прошёл.",
        "error_message":         "Что-то пошло не так. Попробуйте ещё раз.",
        "no_permission":         "⛔ У вас нет прав для этой команды.",
        "btn_dismiss":           "👌 Окей, понятно",

        "recurring_intro":       "📅 Повторяющееся бронирование\n\nКаждый *{weekday}* с *{start}* до *{end}*.\n\n*Шаг 1 — Выберите дату НАЧАЛА:*\n_(Сначала выберите месяц)_",
        "recurring_pick_to":     "✅ Дата начала: *{from_date}*\n\n*Шаг 2 — Выберите дату КОНЦА:*\n_(Сначала выберите месяц)_",
        "recurring_pick_from_day": "📅 *{month}* — выберите день НАЧАЛА:",
        "recurring_pick_to_day": "📅 *{month}* — выберите день КОНЦА:",
        "recurring_enter_title": "📅 *{from_date}* → *{to_date}*\n🗓 Каждый *{weekday}* · {start}–{end}\n\n✏️ *Введите название:*\n_(Например: Еженедельная встреча)_",
        "recurring_preview":     "✅ *Подтвердите повторяющееся бронирование:*\n\n📋 *{title}*\n🗓 Каждый {weekday}\n🕐 {start} – {end}\n📅 {from_date} → {to_date}\n🔢 *{count} броней* будет создано",
        "recurring_success":     "🎉 *{count} повторяющихся броней создано!*\n",
        "recurring_skipped":     "\n⚠️ *{count} дат пропущено* (уже занято):",
        "recurring_cancelled":   "Повторяющееся бронирование отменено.",
        "recurring_title_invalid": "Введите корректное название (1–80 символов).",
        "recurring_pick_from_month": "Выберите месяц НАЧАЛА:",
        "recurring_pick_to_month":   "Выберите месяц КОНЦА:",

        # ── Free time check ──────────────────────────────────────────────

        "free_label":    "🟢 Свободно:",
        "booked_label":  "🔒 Занято:",
        "no_free_label": "🔴 Свободного времени нет.",

        # ── 1 hour reminder ──────────────────────────────────────────────
        "reminder_title":   "⏰ Ваше бронирование начинается через {minutes} минут!",
        "reminder_headsup": "⏰ Клуб занят через {minutes} минут",
    },
    # -----------------------------------------------------------------------
    # ARMENIAN
    # -----------------------------------------------------------------------
    "hy": {
        "start_message": "Ներքևում կարող եք տեսնել այս բոտի բոլոր հնարավորությունները 📋 \n\nԵթե ունեք հարցեր, սեղմեք «Օգնություն» կոճակը ℹ️ \n\nՊլանավորեք ձեր ժամանակը խելամտորեն ⏰✨",
        "choose_language":       "🌐 Choose language / Выберите язык / Ընտրեք լեզուն",
        "language_changed":      "✅ Լեզուն փոխվել է հայերենի։",

        "btn_book_office":       "📅 Ամրագրել ակումբը",
        "btn_view_schedule":     "📊 Դիտել գրաֆիկը",
        "btn_my_bookings":       "📌 Իմ ամրագրումները",
        "btn_free_time":         "🟢 Ազատ ժամեր",
        "btn_help":              "ℹ️ Օգնություն",
        "btn_language":          "🌐 Լեզու",

        "help_text":             (
            "ℹ️ *Օգնություն*\n\n"
            "*📅 Ամրագրել ակումբը* — քայլ առ քայլ ամրագրում։\n"
            "*📊 Դիտել գրաֆիկը* — շաբաթական կամ ամսական ամրագրումներ։\n"
            "*📌 Իմ ամրագրումները* — դիտել, խմբագրել կամ չեղարկել ամրագրումները։\n"
            "*🟢 Ազատ ժամեր* — ստուգել ազատ ժամերը։\n\n"
            "Աշխատանքային ժամեր՝ 10:00 – 23:00\n"
            "Առավելագույն ամրագրում՝ 6 ժամ"
        ),

        "choose_month":          "📅 Քայլ 1 4-ից — Ընտրեք ամիսը:",
        "choose_day":            "📅 *{month}* — ընտրեք օրը:",
        "choose_time":           "📅 {date}\n\n🕐 Քայլ 2 4-ից — Ընտրեք մեկնարկի ժամը:",
        "choose_duration":       "📅 {date}  |  🕐 {hour}:00\n\n⏱ Քայլ 3 4-ից — Ընտրեք տևողությունը:",
        "enter_title":           "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ժ\n\n✏️ Քայլ 4 4-ից — Մուտքագրեք անունը: \n\nՕրինակ՝ Սեղանի խաղեր կամ Փոքր խումբ",
        "enter_title_again":     "📅 {date}  |  🕐 {hour}:00  |  ⏱ {duration}ժ\n\n✏️ Քայլ 4 4-ից — Մուտքագրեք անունը: \n\n_Մուտքագրեք միջոցառման անունը_",
        "confirm_preview":       "✅ Հաստատե՞լ ամրագրումը:\n\n📋 {title}\n📅 {date}\n🕐 {start}:00 – {end}:00  ({duration}ժ)\n👤 {user}",
        "booking_confirmed":     "🎉 Ամրագրումը հաստատված է!\n\n{details}",
        "booking_cancelled":     "Ամրագրումը չեղարկված է։",

        "booking_conflict":      (
            "❌ Այս ժամը արդեն զբաղված է!\n\n"
            "Հատվածություն կա հետևյալի հետ.\n\n"
            "🕐 {start} – {end}\n"
            "📋 {title}\n"
            "👤 {user}\n\n"
            "Խնդրում ենք ընտրել այլ ժամ։"
        ),
        "slot_taken_alert":      "⛔ Այս ժամը արդեն զբաղված է։",
        "slot_taken_detail":     "🔒 Արդեն զբաղված է!\n\n📋 {title}\n🕐 {start} – {end}\n👤 {user}",

        "group_notification":    "📢 Ակումբի նոր ամրագրում\n\n📅 {day}\n🕐 {start} – {end}\n\n📋 {title}\n👤 Ամրագրում է: {user}",

        "my_bookings_title":     "📌 Իմ ամրագրումները — սեղմեք կառավարելու համար.",
        "my_bookings_empty":     "📌 Իմ ամրագրումները\n\nԴուք չունեք առաջիկա ամրագրումներ։",
        "booking_not_found":     "Ամրագրումը չի գտնվել։",
        "booking_deleted":       "✅ Ամրագրումը չեղարկված է։",
        "booking_delete_failed": "❌ Չհաջողվեց չեղարկել. {reason}",
        "btn_delete_all":        "🗑 Չեղարկել իմ բոլոր ամրագրումները",
        "btn_delete_all_yes":    "✅ Այո, չեղարկել ամբողջը",
        "delete_all_confirm":    "⚠️ Չեղարկե՞լ ամբողջը\n\nՍա կջնջի թվով {count} ձեր բոլոր ամրագրումները։",
        "delete_all_done":       "✅ Կատարված է։",


        "edit_title":            "✏️ Խմբագրել ամրագրումը — ինչ փոխե՞լ:",
        "edit_pick_duration":    "Ընթացիկ տևողություն՝ *{duration}ժ*\n\nԸնտրեք նոր տևողություն:",
        "edit_pick_start_time":  "Ընթացիկ ժամ՝ *{start_time}*\n\nԸնտրեք նոր ժամ:",
        "edit_pick_date":        "Ընթացիկ ամսաթիվ՝ *{date}*\n\nԸնտրեք նոր ամսաթիվ:",
        "edit_pick_title":       "Ընթացիկ անուն՝ *{title}*\n\nՄուտքագրեք նոր անուն:",
        "edit_updated":          "✅ Թարմացված է!\n\n{details}",
        "edit_title_updated":    "✅ Անունը թարմացված է!\n\n{details}",
        "edit_failed":           "❌ {reason}",
        "edit_cancelled":        "Խմբագրումը չեղարկված է։",
        "edit_unknown_action":   "Անհայտ գործողություն։",
        "edit_unexpected_input": "Անսպասելի մուտք։ Օգտագործեք կոճակները։",

        "btn_edit":              "✏️ Խմբագրել",
        "btn_delete":            "🗑 Չեղարկել ամրագրումը",
        "btn_edit_title":        "✏️ Անուն",
        "btn_edit_date":         "📅 Ամսաթիվ",
        "btn_edit_start_time":   "🕐 Մեկնարկի ժամ",
        "btn_edit_duration":     "⏱ Տևողություն",
        "btn_my_bookings_back":  "← Իմ ամրագրումները",

        "btn_back":              "←  Հետ",
        "btn_cancel":            "✖  Չեղարկել",
        "btn_confirm":           "✅  Հաստատել",
        "btn_menu":              "←  Մենյու",
        "btn_change_title":      "←  Փոխել անունը",

        "schedule_title":        "📊 Գրաֆիկ — ընտրեք ժամանակահատված:",
        "btn_this_week":         "📅 Այս շաբաթ",
        "btn_next_week":         "📅 Հաջորդ շաբաթ",
        "btn_this_month":        "📆 Այս ամիս",
        "btn_next_month":        "📆 Հաջորդ ամիս",
        "no_bookings_this_month":"Այս ամիս ամրագրումներ չկան։",
        "no_bookings_day":       "📭 Այս օրվա համար ամրագրումներ չկան։",

        "free_time_title":       "🟢 Ազատ ժամեր — ընտրեք օր:",
        "free_slots_header":     "🟢 Ազատ ժամեր {day}:\n",
        "no_free_slots":         "Ազատ ժամ չկա։",

        "title_empty":           "Խնդրում ենք մուտքագրել միջոցառման անունը։",
        "title_too_long":        "Անունը շատ երկար է ({length} նիշ)։ Առավելագույնը 80 նիշ։",
        "title_invalid":         "Սխալ անուն (1–80 նիշ)։ Խնդրում ենք փորձել կրկին։",
        "past_day_alert":        "Այդ օրն արդեն անցել է։",
        "error_message":         "Ինչ-որ բան սխալ գնաց։ Խնդրում ենք փորձել կրկին։",
        "no_permission":         "⛔ Դուք իրավունք չունեք այս հրամանն օգտագործելու։",
        "btn_dismiss":           "👌 Շատ լավ, հասկացա!",

        "recurring_intro":       "📅 *Կրկնվող ամրագրում*\n\nԱմեն *{weekday}* ժամը *{start}*-ից մինչև *{end}*։\n\n*Քայլ 1 — Ընտրեք ՄԵԿՆԱՐԿԻ ամսաթիվը:*\n_(Նախ ընտրեք ամիսը)_",
        "recurring_pick_to":     "✅ Մեկնարկի ամսաթիվ՝ *{from_date}*\n\n*Քայլ 2 — Ընտրեք ԱՎԱՐՏԻ ամսաթիվը:*\n_(Նախ ընտրեք ամիսը)_",
        "recurring_pick_from_day": "📅 *{month}* — ընտրեք ՄԵԿՆԱՐԿԻ օրը:",
        "recurring_pick_to_day": "📅 *{month}* — ընտրեք ԱՎԱՐՏԻ օրը:",
        "recurring_enter_title": "📅 *{from_date}* → *{to_date}*\n🗓 Ամեն *{weekday}* · {start}–{end}\n\n✏️ *Մուտքագրեք անունը:*\n_(Օրինակ՝ Շաբաթական հանդիպում)_",
        "recurring_preview":     "✅ *Հաստատե՞լ կրկնվող ամրագրումը:*\n\n📋 *{title}*\n🗓 Ամեն {weekday}\n🕐 {start} – {end}\n📅 {from_date} → {to_date}\n🔢 *{count} ամրագրում* կստեղծվի",
        "recurring_success":     "🎉 *{count} կրկնվող ամրագրում ստեղծված է!*\n",
        "recurring_skipped":     "\n⚠️ *{count} ամսաթիվ բաց թողնված է* (արդեն զբաղված):",
        "recurring_cancelled":   "Կրկնվող ամրագրումը չեղարկված է։",
        "recurring_title_invalid": "Խնդրում ենք մուտքագրել վավեր անուն (1–80 նիշ)։",
        "recurring_pick_from_month": "Ընտրեք ՄԵԿՆԱՐԿԻ ամիսը:",
        "recurring_pick_to_month":   "Ընտրեք ԱՎԱՐՏԻ ամիսը:",

        # ── Free time check ──────────────────────────────────────────────

        "free_label":    "🟢 Ազատ ժամեր:",
        "booked_label":  "🔒 Զբաղված է:",
        "no_free_label": "🔴 Ազատ ժամ չկա։",


        # ── 1 hour reminder ──────────────────────────────────────────────
        "reminder_title":   "⏰ Ձեր ամրագրումը կսկսի {minutes}-ից։",
        "reminder_headsup": "⏰ Ակումբը զբաղված կլինի {minutes}-ից։",
    },
}


# ===========================================================================
# Month names per language (used in calendar grids)
# ===========================================================================
 
MONTH_NAMES: dict[str, list[str]] = {
    "en": ["January","February","March","April","May","June",
           "July","August","September","October","November","December"],
    "ru": ["Январь","Февраль","Март","Апрель","Май","Июнь",
           "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],
    "hy": ["Հունվար","Փետրվար","Մարտ","Ապրիլ","Մայիս","Հունիս",
           "Հուլիս","Օգոստոս","Սեպտեմբեր","Հոկտեմբեր","Նոյեմբեր","Դեկտեմբեր"],
}
 
# Explicit short abbreviations for month-picker buttons.
# Defined separately so languages where [:3] gives duplicates
# (Armenian: Հունիս/Հուլիս both become Հու) have distinct labels.
MONTH_SHORT: dict[str, list[str]] = {
    "en": ["Jan","Feb","Mar","Apr","May","Jun",
           "Jul","Aug","Sep","Oct","Nov","Dec"],
    "ru": ["Янв","Фев","Мар","Апр","Май","Июн",
           "Июл","Авг","Сен","Окт","Ноя","Дек"],
    "hy": ["Հնվ","Փտր","Մրտ","Ապր","Մյս","Հուն",
           "Հուլ","Օգս","Սեպ","Հկտ","Նյբ","Դկտ"],
}
WEEKDAY_HEADERS: dict[str, list[str]] = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "ru": ["Пн",  "Вт",  "Ср",  "Чт",  "Пт",  "Сб",  "Вс"],
    "hy": ["Երկ", "Երք", "Չոր", "Հնգ", "Ուրբ", "Շբթ", "Կիր"],
}
# Weekday names per language (0=Monday … 6=Sunday)
WEEKDAY_NAMES: dict[str, list[str]] = {
    "en": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    "ru": ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"],
    "hy": ["Երկուշաբթի","Երեքշաբթի","Չորեքշաբթի","Հինգշաբթի","Ուրբաթ","Շաբաթ","Կիրակի"],
}
 
DEFAULT_LANG = "en"

# ===========================================================================
# Public helper function — use this everywhere in the bot
# ===========================================================================

def get_text(lang: str, key: str, **kwargs) -> str:
    """
    Return the localised string for the given key and language.

    Falls back to English if:
      - the language code is unknown
      - the key is missing in the requested language

    Supports keyword format substitution:
        get_text("en", "choose_day", month="March 2026")
        get_text("hy", "booking_conflict", start="15:00", end="18:00",
                 title="Board Games", user="areg")

    Args:
        lang:   language code ("en", "ru", "hy")
        key:    text key (see T dictionary above)
        **kwargs: variables to substitute into the text

    Returns:
        Formatted string ready to send to Telegram.
    """
    text = (
        T.get(lang, T[DEFAULT_LANG])
         .get(key, T[DEFAULT_LANG].get(key, f"[missing text: {key}]"))
    )
    return text.format(**kwargs) if kwargs else text


