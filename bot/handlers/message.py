from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import main_keyboard, cancel_keyboard


# Conversation states for YT downloader
YT_ASK_LINK = 1
YT_SELECT_FORMAT = 2

admin_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Update Routine", callback_data="admin:routine_update")],
    [InlineKeyboardButton("Toggle Routine", callback_data="admin:routine_toggle"), InlineKeyboardButton("Circualte Routine", callback_data="admin:routine_circulate")],
    [InlineKeyboardButton("Edit Schedule", callback_data="admin:schedule_edit"), InlineKeyboardButton("Circulate Schedule", callback_data="admin:schedule_circulate")],
    [InlineKeyboardButton("Publish Notice", callback_data="admin:notice"), InlineKeyboardButton("Show User", callback_data="admin:show_user")],
    [InlineKeyboardButton("Cancel", callback_data="admin:cancel")]
])

admin_toggle_routine_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Confirm", callback_data="admin:toggle_routine:confirm"), InlineKeyboardButton("Cancel", callback_data="admin:toggle_routine:cancel")]
])

resources_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Drive", callback_data="resources:drive"), InlineKeyboardButton("Syllabus", callback_data="resources:syllabus")],
    [InlineKeyboardButton("Cover Page", callback_data="resources:cover_page"), InlineKeyboardButton("CSE website", callback_data="resources:cse_web")],
    [InlineKeyboardButton("Yt-downloader", callback_data="resources:yt_downloader")]
])




routine_path_odd = "resources/routine/routine_odd.png"




async def resources(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("Available resources for CSE:", reply_markup=resources_keyboard)

async def routine(update, context):
    await update.message.reply_photo(
        photo=routine_path_odd,
        caption="Odd week"
    )

async def schedule(update, context):
    await update.message.reply_text("schedule will come soon")

async def admin(update:Update, context:ContextTypes) -> None:
    await update.message.reply_text("Admin Panel: ", reply_markup=admin_keyboard)



async def message_handler(update: Update, context: ContextTypes) -> None:
    user_text = update.message.text
    user_id = update.effective_user.id

    predefined_commands = {
        "Routine": routine,
        "Schedule": schedule,
        "Resources": resources, 
        "Admin": admin
    }
    command = predefined_commands.get(user_text)

    if not command:
        await update.message.reply_text("No Command Found")
        return 
    
    await command(update, context)


# YT Downloader functions
async def yt_downloader_start(update: Update, context: ContextTypes):
    """Handle the Yt-downloader button click - ask for link"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📥 YouTube Downloader\n\nPlease send me a YouTube link to download:",
        reply_markup=cancel_keyboard
    )
    return YT_ASK_LINK


async def yt_receive_link(update: Update, context: ContextTypes):
    """Receive the YouTube link and fetch available formats"""
    user_text = update.message.text
    
    # Validate it's a YouTube URL
    if not any(x in user_text for x in ['youtube.com', 'youtu.be']):
        await update.message.reply_text("❌ This doesn't look like a valid YouTube link. Please try again.")
        return YT_ASK_LINK
    
    # Fetch video info using yt-dlp
    try:
        await update.message.reply_text("🔍 Fetching available formats...")
        
        import yt_dlp
        
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(user_text, download=False)
        
        # Store the URL and info in context
        context.user_data['yt_url'] = user_text
        context.user_data['yt_title'] = info.get('title', 'Unknown')
        
        # Extract and sort formats
        video_formats = []
        audio_formats = []
        
        for fmt in info.get('formats', []):
            # Video formats (with height)
            if fmt.get('height') and fmt.get('vcodec') != 'none':
                video_formats.append({
                    'format_id': fmt.get('format_id'),
                    'height': fmt.get('height', 0),
                    'ext': fmt.get('ext', 'mp4'),
                    'filesize': fmt.get('filesize'),
                    'quality': fmt.get('height', 0)
                })
            # Audio formats
            elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                audio_formats.append({
                    'format_id': fmt.get('format_id'),
                    'abr': fmt.get('abr', 0),
                    'ext': fmt.get('ext', 'm4a'),
                    'quality': fmt.get('abr', 0)
                })
        
        # Sort by quality (high to low)
        video_formats.sort(key=lambda x: x['quality'], reverse=True)
        audio_formats.sort(key=lambda x: x['quality'], reverse=True)
        
        # Remove duplicates based on format_id
        seen_video = set()
        unique_video = []
        for v in video_formats:
            if v['format_id'] not in seen_video:
                seen_video.add(v['format_id'])
                unique_video.append(v)
        
        seen_audio = set()
        unique_audio = []
        for a in audio_formats:
            if a['format_id'] not in seen_audio:
                seen_audio.add(a['format_id'])
                unique_audio.append(a)
        
        context.user_data['yt_video_formats'] = unique_video[:10]  # Limit to top 10
        context.user_data['yt_audio_formats'] = unique_audio[:10]
        
        # Build keyboard with formats
        keyboard = []
        
        # Video section
        if unique_video:
            keyboard.append([InlineKeyboardButton("🎬 VIDEO FORMATS", callback_data="yt:video_header")])
            for i, v in enumerate(unique_video[:5]):  # Top 5 video
                size_str = f" ({v['height']}p)"
                keyboard.append([InlineKeyboardButton(f"Video {size_str}", callback_data=f"yt:download:video:{v['format_id']}:{v['height']}")])
        
        # Audio section
        if unique_audio:
            keyboard.append([InlineKeyboardButton("🎵 AUDIO FORMATS", callback_data="yt:audio_header")])
            for i, a in enumerate(unique_audio[:5]):  # Top 5 audio
                size_str = f" ({int(a['abr'])}kbps)"
                keyboard.append([InlineKeyboardButton(f"Audio {size_str}", callback_data=f"yt:download:audio:{a['format_id']}:{int(a['abr'])}")])
        
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="unversal:cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📹 Title: {info.get('title', 'Unknown')}\n\nSelect a format to download:",
            reply_markup=reply_markup
        )
        
        return YT_SELECT_FORMAT
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching video info: {str(e)}")
        return YT_ASK_LINK


async def yt_download_format(update: Update, context: ContextTypes):
    """Handle format selection and stream to Telegram"""
    query = update.callback_query
    await query.answer("⏳ Downloading and streaming...")
    
    data = query.data.split(':')
    media_type = data[2]  # 'video' or 'audio'
    format_id = data[3]
    quality = data[4]
    
    url = context.user_data.get('yt_url')
    title = context.user_data.get('yt_title', 'video')
    
    if not url:
        await query.edit_message_text("❌ Session expired. Please start over.")
        return None
    
    try:
        import yt_dlp
        import io
        
        await query.edit_message_text(f"⏳ Downloading {media_type} ({quality})...\n\nThis may take a while depending on the file size.")
        
        # Create a buffer to hold the video
        video_buffer = io.BytesIO()
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                    # Optionally update status
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': '-',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
        }
        
        # Download and capture output
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Get the direct URL for the format
            for fmt in info.get('formats', []):
                if fmt.get('format_id') == format_id:
                    direct_url = fmt.get('url')
                    break
            
            if not direct_url:
                await query.edit_message_text("❌ Could not find download URL.")
                return None
            
            # Download using requests to get proper control
            import requests
            response = requests.get(direct_url, stream=True, timeout=60)
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    video_buffer.write(chunk)
        
        # Get the video data
        video_data = video_buffer.getvalue()
        
        if not video_data:
            await query.edit_message_text("❌ Failed to download video.")
            return None
        
        # Send to Telegram
        video_buffer.seek(0)
        
        ext = 'mp4' if media_type == 'video' else 'm4a'
        filename = f"{title}.{ext}"
        
        if media_type == 'video':
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video_buffer,
                filename=filename,
                caption=f"📹 {title}\nQuality: {quality}p",
                reply_to_message_id=query.message.message_id
            )
        else:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=video_buffer,
                filename=filename,
                caption=f"🎵 {title}\nQuality: {quality}kbps",
                reply_to_message_id=query.message.message_id
            )
        
        await query.edit_message_text(f"✅ Successfully sent!")
        return None
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")
        return None


async def cancel_yt(update: Update, context: ContextTypes):
    """Cancel the YT downloader conversation"""
    query = update.callback_query
    await query.answer("Cancelled")
    await query.edit_message_text("Operation cancelled.")
    context.user_data.clear()
    return None
