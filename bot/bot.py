from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from bot.handlers.starter import start
from bot.handlers.message import message_handler, handle_format_selection
from config import TELEGRAM_BOT_TOKEN


TOKEN = TELEGRAM_BOT_TOKEN

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
app.add_handler(CallbackQueryHandler(handle_format_selection))
