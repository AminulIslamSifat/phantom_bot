import os
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes


load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SCREENSHOT_API = os.environ["SCREENSHOT_API"]
USE_WEBHOOK =  os.environ["USE_WEBHOOK"]
ROUTINE_URL_ODD_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-odd-week/"
ROUTINE_URL_EVEN_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-even-week/"
IS_LOCAL = os.environ["IS_LOCAL"]
routine_path_odd_week = "resources/routine/routine_odd_week.png"
routine_path_even_week = "resources/routine/routine_even_week.png"
available_drive = {"1-2" : "https://", "2-1": "https://"}




main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Admin"), KeyboardButton("Resources")]
], resize_keyboard=True)

cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="unversal:cancel")]
])