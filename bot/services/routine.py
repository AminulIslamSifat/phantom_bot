import os
import asyncio
import json
from datetime import date, timedelta
from config import (
    ROUTINE_URL_ODD_WEEK,
    ROUTINE_URL_EVEN_WEEK,
    routine_path_odd_week,
    routine_path_even_week,
    routine_week_selector_path,
    user_data_path
)
from bot.scripts.web_screenshot import take_web_screenshot
from bot.services.storage import get_routine_week
from bot.services.database import update_mongodb_data
from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

    
def update_routine():
    try:
        print("Routine Update started...")
        os.makedirs("resources/routine", exist_ok=True)
        take_web_screenshot(ROUTINE_URL_ODD_WEEK, output_path=routine_path_odd_week)
        take_web_screenshot(ROUTINE_URL_EVEN_WEEK, output_path=routine_path_even_week)
        print("Routine Updated.")
    except Exception as e:
        print(f"Something went wrong while updating the routine. Error Code - {e}")


def is_even_week():
    week = get_routine_week()
    calibration_dates = {"date1": date(2026, 7, 9), "date2": date(2026, 7, 2)}
    calibration_date = calibration_dates["date1"] if week=="even" else calibration_dates["date2"]
    today = date.today()
    day_count = (today - calibration_date).days
    activation_date = today - timedelta(day_count % 7 - 2)
    is_even = (day_count // 7) % 2 == 0
    return (is_even, str(activation_date))


def toggle_routine():
    week = get_routine_week()
    toggled_week = "even" if week=="odd" else "odd"
    data = {
        "id" : "routine_week_selector",
        "week": toggled_week
    }
    with open(routine_week_selector_path, "w") as file:
        json.dump(data, file, indent=4)
    update_mongodb_data("routine_week_selector", data)
    print("Routine toggled successfully")


async def circulate_routine(update: Update, context: ContextTypes) -> None:
    if not os.path.exists(user_data_path):
        return await update.effective_message.reply_text("No user data found.")

    with open(user_data_path, "r") as file:
        user_data = json.load(file)

    active_users = [
        data["user_id"] for data in user_data.values()
        if data["user_id"] is not None
    ]

    is_even, starting_date = is_even_week()
    routine_path = routine_path_even_week if is_even else routine_path_odd_week
    path_extension = "routine-even-week" if is_even else "routine-odd-week"

    routine_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Live Routine", url=f"https://ruet-cse-liart.vercel.app/routine/{path_extension}/")]
    ])

    msg = await update.effective_message.reply_text(
        f"Sending routine to {len(active_users)} people..."
    )

    async def send_one(user_id: int) -> bool:
        try:
            await context.bot.send_photo(
                chat_id=int(user_id),
                photo=routine_path,
                caption=f"This routine is applicable from {starting_date}.",
                reply_markup=routine_keyboard,
            )
            return True
        except Exception as e:
            print(f"Error sending to {user_id}: {e}")
            return False

    results = await asyncio.gather(*(send_one(uid) for uid in active_users))
    success_count = sum(results)

    await msg.edit_text(f"Routine circulated to {success_count}/{len(active_users)} people. ✅")
