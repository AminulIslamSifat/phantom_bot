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
    yt_download_file_id_handler,
    syllabus_id_handler
)
from bot.handlers.conversation import(
    start_yt_downloader,
    receieve_yt_link,
    cancel_yt_downloader,
    ask_for_roll,
    recieve_roll,
    cancel_registration,
    ask_for_notice,
    recieve_notice,
    cancel_notice
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
    entry_points=[CallbackQueryHandler(start_yt_downloader, pattern="^resources:yt_downloader$")],
    states={
        "recieve_yt_link" : [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receieve_yt_link),
            CallbackQueryHandler(cancel_yt_downloader, pattern="^resources:cancel$")
        ]
    },
    fallbacks=[]
))
app.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_for_roll, pattern="^register$")],
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

#specific hadler
app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin:"))
app.add_handler(CallbackQueryHandler(yt_download_file_id_handler, pattern="^resources:yt_downloader:download:", block=False))
app.add_handler(CallbackQueryHandler(syllabus_id_handler, pattern="^(resources:syllabus:official:|resources:syllabus:unofficial:)"))
app.add_handler(CallbackQueryHandler(resources_button_handler, pattern="^resources:"))


#universal message handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
