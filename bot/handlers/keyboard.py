from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)


main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("Routine"), KeyboardButton("Schedule")],
    [KeyboardButton("Admin"), KeyboardButton("Resources")]
], resize_keyboard=True)

