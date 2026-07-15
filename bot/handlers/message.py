from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import main_keyboard, cancel_keyboard




admin_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Update Routine", callback_data="admin:routine_update")],
    [InlineKeyboardButton("Toggle Routine", callback_data="admin:routine_toggle"), InlineKeyboardButton("Circualte Routine", callback_data="admin:routine_circulate")],
    [InlineKeyboardButton("Edit Schedule", callback_data="admin:schedule_edit"), InlineKeyboardButton("Circulate Schedule", callback_data="admin:schedule_circulate")],
    [InlineKeyboardButton("Publish Notice", callback_data="admin:notice"), InlineKeyboardButton("Show User", callback_data="admin:show_user")],
    [InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

admin-toggle_routine_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Confirm", callback_data="admin:toggle_routine:confirm"), InlineKeyboardButton("Cancel", callback_data="admin:toggle_routine:cancel")]
])

resources_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Drive", callback_data="resources:drive"), InlineKeyboardButton("Syllabus", callback_data="resources:syllabus")],
    [InlineKeyboardButton("Cover Page", callback_data="resources:cover_page"), InlineKeyboardButton("CSE website", callback_data="resources:cse_web")]
])




routine_path_odd = "resources/routine/routine_odd.png"




async def resources(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("Available resources for CSE:", reply_markup=resources_keyboard)

async def routine(update, context):
    await update.message.reply_photo(
        photo=routine_path_odd,
        caption="Odd week"
    )

async def schedule(update, context):
    await update.message.reply_text("schedule will come soon")

async def admin(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("Admin Panel: ", reply_markup=admin_keyboard)



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
