from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    main_keyboard, 
    cancel_keyboard, 
    routine_path_even_week, 
    routine_path_odd_week
)
from bot.services.routine import is_even_week
from bot.services.schedule import get_schedule


resources_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Drive", callback_data="resources:drive"), InlineKeyboardButton("Syllabus", callback_data="resources:syllabus")],
    [InlineKeyboardButton("YT-downloader", callback_data="resources:yt_downloader"), InlineKeyboardButton("CSE Archive", url="https://ruetcsearchive.app/")],
    [InlineKeyboardButton("G. Classroom Code", callback_data="resources:goolge_classroom_code"), InlineKeyboardButton("All websites", callback_data="resources:all_websites")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])




async def resources(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("Available resources for CSE:", reply_markup=resources_keyboard)

async def routine(update, context):
    try:
        is_even, starting_date = is_even_week()
        routine_path = routine_path_even_week if is_even else routine_path_odd_week

        path_extension = "routine-even-week" if is_even else "routine-odd-week"
        routine_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Live Routine", url=f"https://ruet-cse-c-routine.vercel.app/{path_extension}/")]
        ])

        await context.bot.send_photo(
            chat_id = update.effective_user.id,
            photo = routine_path,
            caption = f"This routine is applicable from {starting_date}.",
            reply_markup = routine_keyboard
        )
        
    except Exception as e:
        print(f"Routine function error - {e}")

async def schedule(update:Update, context:ContextTypes):
    try:
        schedule_text = get_schedule()
        await update.message.reply_text(
            schedule_text, 
            reply_markup=main_keyboard, 
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Schedule function error - {e}")
        await update.message.reply_text("Failed to get schedule.", reply_markup=main_keyboard)



async def message_handler(update: Update, context: ContextTypes) -> None:
    user_text = update.message.text
    user_id = update.effective_user.id

    predefined_commands = {
        "Routine": routine,
        "Schedule": schedule,
        "Resources": resources,
    }
    command = predefined_commands.get(user_text)

    if not command:
        await update.message.reply_text("No Command Found")
        return 
    
    await command(update, context)
