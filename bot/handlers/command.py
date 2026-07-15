from telegram import Update
from telegram.ext import ContextTypes
from config import main_keyboard


async def start(update:Update, context: ContextTypes) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.last_name}", reply_markup=main_keyboard)