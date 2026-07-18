import os
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import urllib.parse
from telethon import TelegramClient
from telethon.sessions import StringSession
from pathlib import Path


load_dotenv()
IS_LOCAL = os.environ["IS_LOCAL"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN_TEST"] if IS_LOCAL=="True" else os.environ["TELEGRAM_BOT_TOKEN"]
SCREENSHOT_API = os.environ["SCREENSHOT_API"]
USE_WEBHOOK =  os.environ["USE_WEBHOOK"]
ROUTINE_URL_ODD_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-odd-week/"
ROUTINE_URL_EVEN_WEEK = "https://ruet-cse-c-routine.vercel.app/routine-even-week/"
routine_path_odd_week = "resources/routine/routine_odd_week.png"
routine_path_even_week = "resources/routine/routine_even_week.png"
syllabus_official_folder = "resources/syllabus/official/"
syllabus_unofficial_folder = "resources/syllabus/unofficial/"
available_drive = {
    "1-1": "https://drive.google.com/drive/folders/1l7a6E_dt9Jg4woxOiW8EnzHtRGTo0EbP",
    "1-2" : "https://drive.google.com/drive/folders/1ANRGpNCCFHhsQk8MnjHs_cT6Jl4zkcLT", 
    "2-1": "https://drive.google.com/drive/folders/1zxDdCdFiquVKO86oOLXKxMsSCJalHld_"
}
available_g_classroom = {
    "CSE 2101" : "xxxx",
    "CSE 2102" : "yyyy"
}
available_syllabus_official = {}
available_syllabus_unofficial = {}
for file in Path(syllabus_official_folder).iterdir():
    if file.is_file():
        available_syllabus_official[file.stem] = str(file.resolve())
for file in Path(syllabus_unofficial_folder).iterdir():
    if file.is_file():
        available_syllabus_unofficial[file.stem] = str(file.resolve())
MONGODB_USERNAME = urllib.parse.quote_plus(os.environ["MONGODB_USERNAME"])
MONGODB_USER_PASSWORD = urllib.parse.quote_plus(os.environ["MONGODB_USER_PASSWORD"])
mdb_client = MongoClient(f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_USER_PASSWORD}@cluster0.5ckeilq.mongodb.net/?appName=Cluster0")
user_data_path = ".data/user_data.json"
routine_week_selector_path = ".data/routine_odd_even_week.json"
TELETHON_API_ID = os.environ["TELETHON_API_ID"]
TELETHON_API_HASH = os.environ["TELETHON_API_HASH"]
TELETHON_SESSION = os.environ["TELETHON_SESSION"]
TELETHON_SESSION_TEST = os.environ["TELETHON_SESSION_TEST"]
ACTIVE_TELETHON_SESSION = TELETHON_SESSION_TEST if IS_LOCAL=="True" else TELETHON_SESSION
tg_client = TelegramClient(StringSession(ACTIVE_TELETHON_SESSION), TELETHON_API_ID, TELETHON_API_HASH)
PHANTOM_BOT_CHANNEL_ID = int(os.environ["PHANTOM_BOT_CHANNEL_ID"])
MAX_DOWNLOAD_SIZE_BYTES = int(os.environ.get("MAX_DOWNLOAD_SIZE_MB", 500)) * 1024 * 1024
TMP_DIR=".data/tmp/"


main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Cover Page"), KeyboardButton("Resources")]
], resize_keyboard=True)

cancel_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="unversal:cancel")]
])

teacher_data_path = ".data/teacher_data.json"
TEACHER_API_URL = "https://api.nabilsnigdho.dev/teachers"

admin_list = {
    "sifat": 6226239719
}