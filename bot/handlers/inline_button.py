from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
import threading
from telegram.ext import ContextTypes
from config import available_drive
from bot.services.routine import update_routine





#ALL the keyboard are gathered here
admin_toggle_routine_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Confirm", callback_data="admin:toggle_routine:confirm"), InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

resources_drive_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(x, url=y) for x,y in available_drive.items()],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_syllabus_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Official", callback_data="resources:syllabus:official"), InlineKeyboardButton("Unofficial", callback_data="resources:syllabus:unofficial")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_yt_downloader_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_cover_page_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Official", url="https://ruet-cover-page.github.io/"), InlineKeyboardButton("Unofficial", callback_data="resources:cover_page:unofficial")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])



async def admin_button_handler(update:Update, context:ContextTypes) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "admin:routine_toggle":
        await query.edit_message_text("Please make sure if you really want to toggle the routine: ", reply_markup=admin_toggle_routine_keyboard)
    elif query.data == "admin:routine_update":
        await query.edit_message_text("The Routine image will be updated from the website in the background. There won't be any completion notice.\nIf you want to modify the content of the routine then please go to 'Edit Routine'. Thank you.")
        t = threading.Thread(target=update_routine)
        t.start()
    elif query.data == "admin:toggle_routine:confirm":
        await query.edit_message_text("Routine toggle confirmed, Coming soon")
    elif query.data == "admin:notice":
        await query.edit_message_text("Notice is coming soon...")
    elif query.data == "admin:cancel":
        await query.edit_message_text("Request Cancelled.")



async def resources_button_handler(update:Update, context:ContextTypes) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "resources:drive":
        await query.edit_message_text("Currently available drive are listed below: ", reply_markup=resources_drive_keyboard)
    elif query.data == "resources:syllabus":
        await query.edit_message_text("Official syllabus is from RUET, Unofficial one is created manually from class content.", reply_markup=resources_syllabus_keyboard)
    elif query.data == "resources:cover_page":
        await query.edit_message_text("Official is the ruet-cover-page from github, Unofficial is a project of Sec C. You can find your cover page prepared automatically in unofficial section.", reply_markup=resources_cover_page_keyboard)
    elif query.data == "resources:yt_downloader":
        await query.edit_message_text("Enter the link of the video:", reply_markup=resources_yt_downloader_keyboard)
    elif query.data == "resources:cancel":
        await query.edit_message_text("Request Cancelled.")