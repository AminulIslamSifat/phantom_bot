from bot.handlers.command import start, admin, help
from config import TELEGRAM_BOT_TOKEN,tg_client
from bot.handlers.message import message_handler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler, 
    MessageHandler, 
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
from bot.handlers.inline_button import (
    admin_button_handler, 
    resources_button_handler,
    syllabus_id_handler
)
from bot.handlers.conversation import(
    ask_for_roll,
    recieve_roll,
    cancel_registration,
    ask_for_notice,
    recieve_notice,
    cancel_notice
)
from bot.handlers.coverpage import (
    cover_page_start,
    cp_subject_selected,
    cp_teacher_selected,
    cp_experiment_selected,
    cp_experiment_manual_prompt,
    cp_receive_manual_exp,
    cp_receive_dates,
    cp_dates_quick_select,
    cp_cancel,
    SELECT_SUBJECT,
    SELECT_TEACHER,
    SELECT_EXPERIMENT,
    MANUAL_EXP_INPUT,
    ENTER_DATES,
)
import asyncio


TOKEN = TELEGRAM_BOT_TOKEN
async def post_init(app):
    await tg_client.start()
    await tg_client.get_dialogs()  # forces caching of entities incl. channels the account is in


app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

#Command
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("help", help))

#conversations
app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("register", ask_for_roll)],
    states={
        "recieve_roll" : [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recieve_roll),
            CallbackQueryHandler(cancel_registration, pattern="^registration:cancel$")
        ]
    },
    fallbacks=[]
))
app.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_for_notice, pattern="^admin:notice$")],
    states={
        "recieve_notice" : [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recieve_notice),
            CallbackQueryHandler(cancel_notice, pattern="^admin:notice:cancel$")
        ]
    },
    fallbacks=[]
))

# Cover page conversation — entry via reply keyboard "Cover Page" button
app.add_handler(ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^Cover Page$"), cover_page_start)],
    states={
        SELECT_SUBJECT: [
            CallbackQueryHandler(cp_subject_selected, pattern="^coverpage:subject:"),
            CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$"),
        ],
        SELECT_TEACHER: [
            CallbackQueryHandler(cp_teacher_selected, pattern="^coverpage:teacher:"),
            CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$"),
        ],
        SELECT_EXPERIMENT: [
            CallbackQueryHandler(cp_experiment_selected, pattern="^coverpage:exp:(?!manual$)"),
            CallbackQueryHandler(cp_experiment_manual_prompt, pattern="^coverpage:exp:manual$"),
            CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$"),
        ],
        MANUAL_EXP_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cp_receive_manual_exp),
            CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$"),
        ],
        ENTER_DATES: [
            CallbackQueryHandler(cp_dates_quick_select, pattern="^coverpage:dates:"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, cp_receive_dates),
            CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(cp_cancel, pattern="^coverpage:cancel$")],
    allow_reentry=True,
))

#specific hadler
app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin:"))
app.add_handler(CallbackQueryHandler(syllabus_id_handler, pattern="^(resources:syllabus:official:|resources:syllabus:unofficial:)"))
app.add_handler(CallbackQueryHandler(resources_button_handler, pattern="^resources:"))


#universal message handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
