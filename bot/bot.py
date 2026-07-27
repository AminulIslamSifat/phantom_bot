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
    cancel_notice,
    ask_for_share_file,
    receive_share_file,
    cancel_share_file
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


def build_app(with_updater: bool = True):
    """Build the PTB Application. Pass with_updater=False for custom webhook server."""
    builder = ApplicationBuilder().token(TOKEN).post_init(post_init)
    if not with_updater:
        builder = builder.updater(None)
    return builder.build()


def register_handlers(application):
    """Register all bot handlers on a PTB Application instance."""
    # Command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("help", help))

    # Conversations
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("register", ask_for_roll)],
        states={
            "recieve_roll": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recieve_roll),
                CallbackQueryHandler(cancel_registration, pattern="^registration:cancel$")
            ]
        },
        fallbacks=[]
    ))
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_for_notice, pattern="^admin:notice$")],
        states={
            "recieve_notice": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recieve_notice),
                CallbackQueryHandler(cancel_notice, pattern="^admin:notice:cancel$")
            ]
        },
        fallbacks=[]
    ))
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_for_share_file, pattern="^admin:share_file$")],
        states={
            "receive_share_file": [
                MessageHandler(filters.ATTACHMENT, receive_share_file),
                CallbackQueryHandler(cancel_share_file, pattern="^admin:share_file:cancel$")
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_share_file, pattern="^admin:share_file:cancel$")]
    ))

    # Cover page conversation
    application.add_handler(ConversationHandler(
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

    # Specific handlers
    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin:"))
    application.add_handler(CallbackQueryHandler(syllabus_id_handler, pattern="^(resources:syllabus:official:|resources:syllabus:unofficial:)"))
    application.add_handler(CallbackQueryHandler(resources_button_handler, pattern="^resources:"))

    # Universal message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


app = build_app()
register_handlers(app)
