from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import main_keyboard, admin_list, user_data_path
import json
import os



admin_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Update Routine", callback_data="admin:routine_update"), InlineKeyboardButton("Edit Routine", url="https://ruet-cse-liart.vercel.app/routine/editor")],
    [InlineKeyboardButton("Toggle Routine", callback_data="admin:routine_toggle"), InlineKeyboardButton("Circulate Routine", callback_data="admin:routine_circulate")],
    [InlineKeyboardButton("Edit Schedule", url="https://ruet-cse-liart.vercel.app/schedule"), InlineKeyboardButton("Circulate Schedule", callback_data="admin:schedule_circulate")],
    [InlineKeyboardButton("Edit Subject Teacher Data", url="https://ruet-cse-liart.vercel.app/teachers")],
    [InlineKeyboardButton("Edit experiment/Assingment detail", url="https://ruet-cse-liart.vercel.app/experiments")],
    [InlineKeyboardButton("Publish Notice", callback_data="admin:notice"), InlineKeyboardButton("Show User", callback_data="admin:show_user")],
    [InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

help_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Readme", url="https://github.com/AminulIslamSifat/phantom_bot/blob/main/README.md")],
    [InlineKeyboardButton("User Guide", url="https://github.com/AminulIslamSifat/phantom_bot/blob/main/user_guide.md")],
    [InlineKeyboardButton("Developer Guide", url="https://github.com/AminulIslamSifat/phantom_bot/blob/main/developer_helper.md")]
])

register_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Register", callback_data="register")]])


async def start(update:Update, context: ContextTypes) -> None:
    user_id = update.effective_user.id
    active_user = []
    if os.path.exists(user_data_path):
        with open(user_data_path, "r") as file:
            user_data = json.load(file)
    
    for user, data in user_data.items():
        if data["user_id"] != None:
            active_user.append(data["user_id"])
    
    if user_id not in active_user:
        await update.message.reply_text(f"Hello {update.effective_user.last_name}, Please register to use the bot.", reply_markup=register_keyboard)
    else:
        await update.message.reply_text(f"Welcome Back {update.effective_user.last_name}", reply_markup=main_keyboard)


async def help(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("The Guide on how to use this is given below: ")

async def admin(update:Update, context:ContextTypes) -> None:
    user_id = update.effective_user.id
    if user_id not in admin_list.values():
        await update.message.reply_text("Sorry, You are not an admin")
        return
    await update.message.reply_text("Admin Panel: ", reply_markup=admin_keyboard)