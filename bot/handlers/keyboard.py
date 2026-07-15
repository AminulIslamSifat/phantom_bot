from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from config import CANCEL_BUTTON


main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Admin"), KeyboardButton("Resources")]
], resize_keyboard=True)

yt_download_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📹 YouTube Downloader")],
    [KeyboardButton(CANCEL_BUTTON)]
], resize_keyboard=True)

