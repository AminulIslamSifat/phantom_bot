from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
import os
import json
import asyncio
import threading
from telegram.ext import ContextTypes, ConversationHandler
from config import available_drive,tg_client, available_g_classroom, available_syllabus_official, available_syllabus_unofficial, user_data_path
from bot.services.routine import update_routine, toggle_routine
from bot.services.routine import circulate_routine
from bot.services.schedule import circulate_schedule





#ALL the keyboard are gathered here
admin_toggle_routine_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Confirm", callback_data="admin:toggle_routine:confirm"), InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

resources_drive_buttons = [[InlineKeyboardButton(x, url=y)] for x, y in available_drive.items()]
resources_drive_buttons.append([InlineKeyboardButton("Cancel", callback_data="resources:cancel")])
resources_drive_keyboard = InlineKeyboardMarkup(resources_drive_buttons)

resources_syllabus_official_buttons = [[InlineKeyboardButton(x, callback_data=f"resources:syllabus:official:{x}") for x in available_syllabus_official]]
resources_syllabus_official_buttons.append([InlineKeyboardButton("Cancel", callback_data="resources:cancel")])
resources_syllabus_official_keyboard = InlineKeyboardMarkup(resources_syllabus_official_buttons)

resources_syllabus_unofficial_buttons = [[InlineKeyboardButton(x, callback_data=f"resources:syllabus:unofficial:{x}") for x in available_syllabus_official]]
resources_syllabus_unofficial_buttons.append([InlineKeyboardButton("Cancel", callback_data="resources:cancel")])
resources_syllabus_unofficial_keyboard = InlineKeyboardMarkup(resources_syllabus_unofficial_buttons)


resources_syllabus_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Official", callback_data="resources:syllabus:official"), InlineKeyboardButton("Unofficial", callback_data="resources:syllabus:unofficial")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])




#text data
resources_g_classroom_code = "All the available classroom code:"
for x, y in available_g_classroom.items():
    resources_g_classroom_code += f"{x}:\n```{y}```\n"



async def admin_button_handler(update:Update, context:ContextTypes) -> None:
    try:
        query = update.callback_query
        await query.answer()

        if query.data == "admin:routine_toggle":
            await query.edit_message_text("Please make sure if you really want to toggle the routine: ", reply_markup=admin_toggle_routine_keyboard)
        elif query.data == "admin:routine_update":
            await query.edit_message_text("The Routine image will be updated from the website in the background. There won't be any completion notice.\nIf you want to modify the content of the routine then please go to 'Edit Routine'. Thank you.")
            t = threading.Thread(target=update_routine)
            t.start()
        elif query.data == "admin:toggle_routine:confirm":
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, toggle_routine)
            await query.edit_message_text("Routine Toggled Successfully.")
        elif query.data == "admin:circulate_routine":
            print("routine circulation")
            await circulate_routine(update, context)
        elif query.data == "admin:circulate_schedule":
            print("schedule circulation")
            await circulate_schedule(update, context)
        elif query.data == "admin:show_user":
            user_list_text = list_user()
            await query.edit_message_text(user_list_text)
        elif query.data == "admin:cancel":
            await query.edit_message_text("Request Cancelled.")
    except Exception as e:
        print(f"Error in admin_button_handler. Error code - {e}")



async def resources_button_handler(update:Update, context:ContextTypes) -> None:
    try:
        query = update.callback_query
        await query.answer()

        if query.data == "resources:drive":
            await query.edit_message_text("Currently available drive are listed below: ", reply_markup=resources_drive_keyboard)
        elif query.data == "resources:syllabus":
            await query.edit_message_text("Official syllabus is from RUET, Unofficial one is created manually from class content.", reply_markup=resources_syllabus_keyboard)
        elif query.data == "resources:syllabus:official":
            await query.edit_message_text("Available Official syllabuses: ", reply_markup=resources_syllabus_official_keyboard)
        elif query.data == "resources:syllabus:unofficial":
            await query.edit_message_text("Avilable Unofficial syllabuses: ", reply_markup=resources_syllabus_unofficial_keyboard)
        elif query.data == "resources:goolge_classroom_code":
            await query.edit_message_text(resources_g_classroom_code, parse_mode="MarkdownV2")
        elif query.data == "resources:all_websites":
            await query.edit_message_text("No websites added. Try again later.")
        elif query.data == "resources:cancel":
            await query.edit_message_text("Request Cancelled.")
    except Exception as e:
        print(f"Error in resources_button_handler. Error code - {e}")

        
async def syllabus_id_handler(update:Update, context:ContextTypes) -> None:
    try:
        query = update.callback_query
        await query.answer()
        chat_id = update.effective_chat.id

        if query.data.startswith("resources:syllabus:official:"):
            syllabus_key = query.data.split(":")[-1]
            syllabus_path = available_syllabus_official[syllabus_key]

            if os.path.exists(syllabus_path):
                await context.bot.send_document(
                    chat_id = chat_id,
                    document = open(syllabus_path, "rb"),
                    caption = f"Here is your syllabus for {syllabus_key}"
                )
        elif query.data.startswith("resources:syllabus:unofficial:"):
            syllabus_key = query.data.split(":")[-1]
            syllabus_path = available_syllabus_unofficial[syllabus_key]

            if os.path.exists(syllabus_path):
                await context.bot.send_document(
                    chat_id = chat_id,
                    document = open(syllabus_path, "rb"),
                    caption = f"Here is your syllabus for {syllabus_key}"
                )
    except Exception as e:
        print(f"Error in syllabus_id_hadler. Error code - {e}")




def list_user():
    if os.path.exists(user_data_path):
        with open(user_data_path, "r") as file:
            user_data = json.load(file)
    user_list_text = ""
    for user, data in user_data.items():
        if data["user_id"] != None:
            user_list_text += f"{user} : {data['user_id']}\n"
    
    return user_list_text
    
    

    
     