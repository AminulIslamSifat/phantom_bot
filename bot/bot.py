from bot.handlers.command import start
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
    start_yt_downloader, 
    receieve_yt_link,
    yt_download_file_id_handler,
    cancel_yt_downloader
)
import asyncio


TOKEN = TELEGRAM_BOT_TOKEN
async def post_init(app):
    await tg_client.start()
    await tg_client.get_dialogs()  # forces caching of entities incl. channels the account is in


app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

#Command
app.add_handler(CommandHandler("start", start))

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

#specific hadler
app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin:"))
app.add_handler(CallbackQueryHandler(yt_download_file_id_handler, pattern="^resources:yt_downloader:download:", block=False))
app.add_handler(CallbackQueryHandler(resources_button_handler, pattern="^resources:"))


#universal message handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
