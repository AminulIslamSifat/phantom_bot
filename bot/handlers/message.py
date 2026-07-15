from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.starter import routine, schedule, admin, resources
from bot.handlers.keyboard import yt_download_keyboard, main_keyboard
from config import CANCEL_BUTTON
import yt_dlp
import tempfile
import os

WAITING_FOR_LINK = 1

async def message_handler(update: Update, context: ContextTypes) -> None:
    user_text = update.message.text
    user_id = update.effective_user.id

    # Check if user is in YT downloader conversation
    if context.user_data.get('yt_state') == WAITING_FOR_LINK:
        if user_text == CANCEL_BUTTON:
            context.user_data['yt_state'] = None
            await update.message.reply_text("Cancelled.", reply_markup=main_keyboard)
            return
        
        # User sent a YouTube link
        await update.message.reply_text("Processing your link... Please wait.")
        await process_youtube_link(update, context, user_text)
        return

    predefined_commands = {
        "Routine": routine,
        "Schedule": schedule,
        "Resources": resources, 
        "Admin": admin,
        "📹 YouTube Downloader": start_yt_download
    }
    command = predefined_commands.get(user_text)

    if not command:
        await update.message.reply_text("No Command Found")
        return
    
    await command(update, context)


async def start_yt_download(update: Update, context: ContextTypes):
    context.user_data['yt_state'] = WAITING_FOR_LINK
    await update.message.reply_text(
        "Please send me a YouTube link:",
        reply_markup=yt_download_keyboard
    )


async def process_youtube_link(update: Update, context: ContextTypes, url: str):
    """Fetch video info and present format options"""
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            await update.message.reply_text("Could not fetch video information.")
            return
        
        # Separate video and audio formats
        video_formats = []
        audio_formats = []
        
        for fmt in info.get('formats', []):
            # Video formats (with height and has audio)
            if fmt.get('height') and fmt.get('acodec') and fmt.get('acodec') != 'none':
                video_formats.append({
                    'format_id': fmt.get('format_id'),
                    'resolution': f"{fmt.get('height')}p",
                    'ext': fmt.get('ext', 'mp4'),
                    'filesize': fmt.get('filesize'),
                    'has_audio': True
                })
            # Audio formats (audio only, no video)
            elif fmt.get('acodec') and fmt.get('acodec') != 'none' and (not fmt.get('vcodec') or fmt.get('vcodec') == 'none'):
                audio_formats.append({
                    'format_id': fmt.get('format_id'),
                    'abr': fmt.get('abr', 0),
                    'ext': fmt.get('ext', 'm4a'),
                })
        
        # Sort video formats by resolution (high to low)
        video_formats.sort(key=lambda x: int(x['resolution'].replace('p', '0')) if x['resolution'].replace('p', '').isdigit() else 0, reverse=True)
        
        # Sort audio formats by bitrate (high to low)
        audio_formats.sort(key=lambda x: x['abr'], reverse=True)
        
        # Remove duplicates based on format_id
        seen_video = set()
        unique_video_formats = []
        for v in video_formats:
            if v['format_id'] not in seen_video:
                seen_video.add(v['format_id'])
                unique_video_formats.append(v)
        
        seen_audio = set()
        unique_audio_formats = []
        for a in audio_formats:
            if a['format_id'] not in seen_audio:
                seen_audio.add(a['format_id'])
                unique_audio_formats.append(a)
        
        # Limit to top 10 of each
        unique_video_formats = unique_video_formats[:10]
        unique_audio_formats = unique_audio_formats[:10]
        
        if not unique_video_formats and not unique_audio_formats:
            await update.message.reply_text("No downloadable formats found.")
            return
        
        # Store URL in context for later use
        context.user_data['yt_url'] = url
        
        # Create inline keyboard with format buttons
        keyboard = []
        
        # Video section
        if unique_video_formats:
            keyboard.append([InlineKeyboardButton("🎬 VIDEO FORMATS", callback_data="video_header")])
            for fmt in unique_video_formats:
                size_str = ""
                if fmt['filesize']:
                    size_mb = fmt['filesize'] / (1024 * 1024)
                    size_str = f" ({size_mb:.1f} MB)"
                btn_text = f"{fmt['resolution']} - {fmt['ext']}{size_str}"
                callback_data = f"video:{fmt['format_id']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
        # Audio section
        if unique_audio_formats:
            keyboard.append([InlineKeyboardButton("🎵 AUDIO FORMATS", callback_data="audio_header")])
            for fmt in unique_audio_formats:
                btn_text = f"{int(fmt['abr'])}kbps - {fmt['ext']}"
                callback_data = f"audio:{fmt['format_id']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton(CANCEL_BUTTON, callback_data="cancel_download")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        title = info.get('title', 'Unknown Title')
        duration = info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
        
        caption = f"📺 **{title}**\n⏱ Duration: {duration_str}\n\nSelect a format to download:"
        
        await update.message.reply_text(caption, reply_markup=reply_markup)
        
    except Exception as e:
        await update.message.reply_text(f"Error processing link: {str(e)}")


async def handle_format_selection(update: Update, context: ContextTypes):
    """Handle user's format selection and stream to Telegram"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cancel_download":
        await query.edit_message_text("Download cancelled.", reply_markup=main_keyboard)
        context.user_data['yt_state'] = None
        context.user_data.pop('yt_url', None)
        return
    
    if data.endswith("_header"):
        return
    
    parts = data.split(':', 1)
    if len(parts) != 2:
        await query.edit_message_text("Invalid format selected.")
        return
    
    media_type, format_id = parts
    
    # Get the stored URL
    url = context.user_data.get('yt_url')
    if not url:
        await query.edit_message_text("Session expired. Please send the link again.")
        return
    
    await query.edit_message_text("Starting download and upload to Telegram...")
    
    try:
        # Create a temporary file path pattern
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }
        
        # Download the file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        # Send file to Telegram
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Check file size limit (Telegram allows up to 50MB for bots)
        if file_size > 50 * 1024 * 1024:
            await query.edit_message_text(f"File too large ({file_size / (1024*1024):.1f} MB). Telegram limit is 50 MB.")
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rmdir(temp_dir)
            return
        
        # Send as video or audio based on type
        if media_type == "video":
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=video_file,
                    caption=f"📺 {info.get('title', 'Video')}",
                    reply_markup=main_keyboard
                )
        else:
            with open(file_path, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio_file,
                    caption=f"🎵 {info.get('title', 'Audio')}",
                    reply_markup=main_keyboard
                )
        
        # Clean up
        os.remove(file_path)
        os.rmdir(temp_dir)
        
        await query.edit_message_text("Upload complete!")
        
    except Exception as e:
        await query.edit_message_text(f"Error during download/upload: {str(e)}")
