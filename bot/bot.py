from bot.handlers.command import start
from config import TELEGRAM_BOT_TOKEN
from bot.handlers.message import message_handler, yt_downloader_start, yt_receive_link, yt_download_format, cancel_yt
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)



TOKEN = TELEGRAM_BOT_TOKEN

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

# YT Downloader conversation handler
yt_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(yt_downloader_start, pattern="^resources:yt_downloader$")],
    states={
        1: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_link)],
        2: [CallbackQueryHandler(yt_download_format, pattern="^yt:download:")],
    },
    fallbacks=[CallbackQueryHandler(cancel_yt, pattern="^(unversal:cancel|admin:cancel)$")],
    allow_reentry=False
)
app.add_handler(yt_conv_handler)


