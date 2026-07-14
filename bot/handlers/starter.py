from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.keyboard import main_keyboard



routine_path_odd = "resources/routine/routine_odd.png"


async def start(update:Update, context: ContextTypes) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.last_name}", reply_markup=main_keyboard)


async def resources(update, context):
    await update.message.reply_text("Resources will come soon")

async def routine(update, context):
    await update.message.reply_photo(
        photo=routine_path_odd,
        caption="Odd week"
    )

async def schedule(update, context):
    await update.message.reply_text("schedule will come soon")

async def admin(update, context):
    await update.message.reply_text("admin will come soon")