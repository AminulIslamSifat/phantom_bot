import os
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes


load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SCREENSHOT_API = os.environ["SCREENSHOT_API"]
USE_WEBHOOK =  os.environ["USE_WEBHOOK"]
ROUTINE_URL = "https://ruet-cse-c-routine.vercel.app/"
IS_LOCAL = os.environ["IS_LOCAL"]


main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Admin"), KeyboardButton("Resources")]
], resize_keyboard=True)

cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="unversal:cancel")]
])