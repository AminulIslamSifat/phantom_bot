from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.starter import routine, schedule, admin, resources

async def message_handler(update: Update, context: ContextTypes) -> None:
    user_text = update.message.text
    user_id = update.effective_user.id

    predefined_commands = {
        "Routine": routine,
        "Schedule": schedule,
        "Resources": resources, 
        "Admin": admin
    }
    command = predefined_commands.get(user_text)

    if not command:
        await update.message.reply_text("No Command Found")
        return 
    
    await command(update, context)
