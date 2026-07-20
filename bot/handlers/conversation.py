from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import asyncio
from config import user_data_path
import os
from bot.services.database import load_users, set_user_telegram_id
import json



registration_cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="registration:cancel")]
])

notice_cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="admin:notice:cancel")]
])



#Notice publisher conversation from admin:notice
async def ask_for_notice(update:Update, context:ContextTypes) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please Enter the notice: ", reply_markup=notice_cancel_keyboard)
    return "recieve_notice"

async def recieve_notice(update:Update, context:ContextTypes) -> None:
    text = update.message.text
    if os.path.exists(user_data_path):
        with open(user_data_path, "r") as file:
            user_data = json.load(file)
    active_users = []
    for user, data in user_data.items():
        if data["user_id"] != None:
            active_users.append(data["user_id"])

    count = 0
    message = await update.message.reply_text(f"Please wait...\nThe routine is been sent to {count} person")

    for user_id in active_users:
        await context.bot.send_message(
            chat_id = int(user_id),
            text = "NOTICE:\n\n" + text
        )
        count += 1
        await message.edit_text(f"Please wait...\nThe notice is been sent to {count} person")
    await message.edit_text(f"The notice is circulated to {len(active_users)} people.")
    return ConversationHandler.END


async def cancel_notice(update:Update, context:ContextTypes):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Notice Cancelled.")
    return ConversationHandler.END


#Registration conversation
async def ask_for_roll(update:Update, context:ContextTypes) -> None:
    try:
        await update.message.reply_text("Please Enter your roll number (2400000): ", reply_markup=registration_cancel_keyboard)
        return "recieve_roll"
    except Exception as e:
        print(f"Error in ask_for_roll function, Error code - {e}")
    
async def recieve_roll(update:Update, context:ContextTypes) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    try:
        roll = int(text)
    except Exception:
        await update.message.reply_text("Please enter a valid roll number. Example: 2400000\n\nRoll:")
        return "recieve_roll"

    if not (2403001 <= roll <= 2403180 or roll == 2400000):
        await update.message.reply_text("Sorry, You are not eligible to use this bot.")
        return ConversationHandler.END

    if not set_user_telegram_id(str(roll), user_id):
        await update.message.reply_text("Sorry, your roll number was not found in the database. Contact an admin.")
        return ConversationHandler.END

    load_users()

    await update.message.reply_text("Registration Complete. If you entered the wrong roll number you can register again by using /register command.")
    return ConversationHandler.END


async def cancel_registration(update:Update, context:ContextTypes):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Registration Cancelled.")
    return ConversationHandler.END