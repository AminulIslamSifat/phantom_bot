from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.scripts.yt_downloader import get_available_video_formats
import asyncio
from config import user_data_path
import os
from bot.services.database import load_users, set_user_telegram_id
import json



# YT downloader conversation from resources:yt_downloader
resources_yt_downloader_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

registration_cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="registration:cancel")]
])

notice_cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="admin:notice:cancel")]
])


async def start_yt_downloader(update:Update, context:ContextTypes) -> None:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter the link of the video:", reply_markup=resources_yt_downloader_keyboard)
    return "recieve_yt_link"

async def receieve_yt_link(update:Update, context:ContextTypes) -> None:
    link = update.message.text

    if not link.startswith(("http://", "https://")):
        await update.message.reply_text("Please upload a valid link (with https://).")
        return "recieve_yt_link"
    context.user_data["yt_link"] = link

    message = await update.message.reply_text("Fetching all the downloadable formats...")

    try:
        loop = asyncio.get_running_loop()
        format_map = await loop.run_in_executor(None, get_available_video_formats, link)
    except Exception as e:
        print(f"Error fetching formats: {e}")
        await message.edit_text("❌ Error fetching available formats.")
        return ConversationHandler.END

    if not format_map:
        await message.edit_text("❌ Failed to fetch video formats. Please make sure the link is correct.")
        return ConversationHandler.END

    formats_keyboard_list = []
    for label, (fid, size) in format_map.items():
        # Compact callback: v|TIER_LABEL for video, a for audio
        # Telegram callback_data limit is 64 bytes - longest: "resources:yt_downloader:download:v|1440p" = 42 bytes
        if label.startswith("Audio"):
            cb = "resources:yt_downloader:download:a"
        else:
            cb = f"resources:yt_downloader:download:v|{label}"
        formats_keyboard_list.append([InlineKeyboardButton(f"{label} : {size}", callback_data=cb)])
    formats_keyboard_list.append([InlineKeyboardButton("Cancel", callback_data="resources:cancel")])
    formats_keyboard = InlineKeyboardMarkup(formats_keyboard_list)

    await message.edit_text("Available formats to download: ", reply_markup=formats_keyboard)
    return ConversationHandler.END

async def cancel_yt_downloader(update: Update, context: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Request Cancelled.")
    return ConversationHandler.END



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