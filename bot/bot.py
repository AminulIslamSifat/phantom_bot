from bot.handlers.command import start
from config import TELEGRAM_BOT_TOKEN
from bot.handlers.message import message_handler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler, 
    MessageHandler, 
    filters,
    CallbackQueryHandler
)
from bot.handlers.inline_button import (
    admin_button_handler, 
    resources_button_handler
)


TOKEN = TELEGRAM_BOT_TOKEN

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin:"))
app.add_handler(CallbackQueryHandler(resources_button_handler, pattern="^resources:"))