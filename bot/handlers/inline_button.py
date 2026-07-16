from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
import asyncio
import threading
from telegram.ext import ContextTypes, ConversationHandler
from config import available_drive,tg_client
from bot.services.routine import update_routine, toggle_routine
from bot.scripts.yt_downloader import get_available_video_formats, download_and_upload





#ALL the keyboard are gathered here
admin_toggle_routine_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Confirm", callback_data="admin:toggle_routine:confirm"), InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

resources_drive_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(x, url=y) for x,y in available_drive.items()],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_syllabus_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Official", callback_data="resources:syllabus:official"), InlineKeyboardButton("Unofficial", callback_data="resources:syllabus:unofficial")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_yt_downloader_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])

resources_cover_page_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Official", url="https://ruet-cover-page.github.io/"), InlineKeyboardButton("Unofficial", callback_data="resources:cover_page:unofficial")],
    [InlineKeyboardButton("Cancel", callback_data="resources:cancel")]
])



async def admin_button_handler(update:Update, context:ContextTypes) -> None:
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
    elif query.data == "admin:notice":
        await query.edit_message_text("Notice is coming soon...")
    elif query.data == "admin:cancel":
        await query.edit_message_text("Request Cancelled.")



async def resources_button_handler(update:Update, context:ContextTypes) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "resources:drive":
        await query.edit_message_text("Currently available drive are listed below: ", reply_markup=resources_drive_keyboard)
    elif query.data == "resources:syllabus":
        await query.edit_message_text("Official syllabus is from RUET, Unofficial one is created manually from class content.", reply_markup=resources_syllabus_keyboard)
    elif query.data == "resources:cover_page":
        await query.edit_message_text("Official is the ruet-cover-page from github, Unofficial is a project of Sec C. You can find your cover page prepared automatically in unofficial section.", reply_markup=resources_cover_page_keyboard)        
    elif query.data == "resources:cancel":
        await query.edit_message_text("Request Cancelled.")


async def yt_download_file_id_handler(update: Update, context: ContextTypes) -> None:
    query = update.callback_query
    chat_id = update.effective_chat.id
    await query.answer()

    link = context.user_data.get("yt_link")
    if not link:
        await update.effective_message.reply_text("Session Expired. Please try again.")
        return

    # Tier-to-max-height map (must match get_available_video_formats)
    TIER_MAX = {"4K": 2160, "1440p": 1440, "1080p": 1080, "720p": 720,
                "480p": 480, "360p": 360, "240p": 240, "144p": 144}

    raw = query.data.split(":")[-1]  # e.g. "v|1080p" or "a"
    if raw.startswith("v|"):
        tier = raw[2:]
        tier_max = TIER_MAX.get(tier, 720)
        format_selector = f"best[height<={tier_max}]/bestvideo[height<={tier_max}]+bestaudio/best"
        label = tier
    else:
        format_selector = "bestaudio/best"
        label = "Audio"

    await query.edit_message_text(f"Format: {label}\nDownload Started...")
    await download_and_upload(context.bot, chat_id, link, format_selector)




#Conversations
async def start_yt_downloader(update:Update, context:ContextTypes) -> None:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Enter the link of the video:", reply_markup=resources_yt_downloader_keyboard)
    return "recieve_yt_link"

async def receieve_yt_link(update:Update, context:ContextTypes) -> None:
    link = update.message.text

    if not link.startswith(("http://", "https://")):
        await update.message.reply_text("Please upload a valid link (with https://).")
        return "recieve_yt_link"
    context.user_data["yt_link"] = link

    message = await update.message.reply_text("Fetching all the downloadable formats...")

    try:
        loop = asyncio.get_running_loop()
        format_map = await loop.run_in_executor(None, get_available_video_formats, link)
    except Exception as e:
        print(f"Error fetching formats: {e}")
        await message.edit_text("❌ Error fetching available formats.")
        return ConversationHandler.END

    if not format_map:
        await message.edit_text("❌ Failed to fetch video formats. Please make sure the link is correct.")
        return ConversationHandler.END

    formats_keyboard_list = []
    for label, (fid, size) in format_map.items():
        # Compact callback: v|TIER_LABEL for video, a for audio
        # Telegram callback_data limit is 64 bytes - longest: "resources:yt_downloader:download:v|1440p" = 42 bytes
        if label.startswith("Audio"):
            cb = "resources:yt_downloader:download:a"
        else:
            cb = f"resources:yt_downloader:download:v|{label}"
        formats_keyboard_list.append([InlineKeyboardButton(f"{label} : {size}", callback_data=cb)])
    formats_keyboard_list.append([InlineKeyboardButton("Cancel", callback_data="resources:cancel")])
    formats_keyboard = InlineKeyboardMarkup(formats_keyboard_list)

    await message.edit_text("Available formats to download: ", reply_markup=formats_keyboard)
    return ConversationHandler.END

async def cancel_yt_downloader(update: Update, context: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Request Cancelled.")
    return ConversationHandler.END
