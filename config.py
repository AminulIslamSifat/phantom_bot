import os
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import urllib.parse
from telethon import TelegramClient
from telethon.sessions import StringSession


load_dotenv()
IS_LOCAL = os.environ["IS_LOCAL"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN_TEST"] if IS_LOCAL=="True" else os.environ["TELEGRAM_BOT_TOKEN"]
print(TELEGRAM_BOT_TOKEN)
SCREENSHOT_API = os.environ["SCREENSHOT_API"]
USE_WEBHOOK =  os.environ["USE_WEBHOOK"]
ROUTINE_URL_ODD_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-odd-week/"
ROUTINE_URL_EVEN_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-even-week/"
routine_path_odd_week = "resources/routine/routine_odd_week.png"
routine_path_even_week = "resources/routine/routine_even_week.png"
available_drive = {"1-2" : "https://", "2-1": "https://"}
MONGODB_USERNAME = urllib.parse.quote_plus(os.environ["MONGODB_USERNAME"])
MONGODB_USER_PASSWORD = urllib.parse.quote_plus(os.environ["MONGODB_USER_PASSWORD"])
mdb_client = MongoClient(f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_USER_PASSWORD}@cluster0.5ckeilq.mongodb.net/?appName=Cluster0")
user_data_path = ".data/user_data.json"
routine_week_selector_path = ".data/routine_odd_even_week.json"
TELETHON_API_ID = os.environ["TELETHON_API_ID"]
TELETHON_API_HASH = os.environ["TELETHON_API_HASH"]
TELETHON_SESSION = os.environ["TELETHON_SESSION"]
tg_client = TelegramClient(StringSession(TELETHON_SESSION), TELETHON_API_ID, TELETHON_API_HASH)
PHANTOM_BOT_CHANNEL_ID = int(os.environ["PHANTOM_BOT_CHANNEL_ID"])
MAX_DOWNLOAD_SIZE_BYTES = int(os.environ.get("MAX_DOWNLOAD_SIZE_MB", 500)) * 1024 * 1024
TMP_DIR=".data/tmp/"


main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Admin"), KeyboardButton("Resources")]
], resize_keyboard=True)

cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="unversal:cancel")]
])

