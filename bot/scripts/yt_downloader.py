import os
import time
import yt_dlp
import asyncio
from typing import Dict, Tuple
from config import tg_client, PHANTOM_BOT_CHANNEL_ID, TMP_DIR, MAX_DOWNLOAD_SIZE_BYTES
try:
    from config import YT_COOKIES_FILE, YT_COOKIES_BROWSER  # optional cookie file / copied browser profile
except ImportError:
    YT_COOKIES_FILE = None
    YT_COOKIES_BROWSER = None
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo


def _apply_yt_cookies(ydl_opts: Dict) -> None:
    ydl_opts.setdefault("remote_components", ["ejs:github"])
    if YT_COOKIES_FILE and os.path.isfile(YT_COOKIES_FILE):
        ydl_opts["cookiefile"] = YT_COOKIES_FILE
    elif YT_COOKIES_BROWSER:
        ydl_opts["cookiesfrombrowser"] = YT_COOKIES_BROWSER

def get_available_video_formats(link: str) -> Dict[str, Tuple[str, str]]:
    """Returns {label: (format_selector, size)} sorted high to low.
    Uses resolution-based format selectors instead of raw format IDs
    to avoid issues with ephemeral/session-specific IDs on streaming sites.
    Snaps available heights to standard resolution tiers for clean display.
    """

    # Standard resolution tiers (label -> max height to qualify)
    STANDARD_TIERS = [
        ("4K",    2160),
        ("1440p", 1440),
        ("1080p", 1080),
        ("720p",  720),
        ("480p",  480),
        ("360p",  360),
        ("240p",  240),
        ("144p",  144),
    ]

    ydl_opts = {'quiet': True, 'no_warnings': True}
    _apply_yt_cookies(ydl_opts)

    def fmt_size(bytes_val):
        if not bytes_val:
            return "N/A"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} TB"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
        except Exception as e:
            print(f"[yt_downloader] extract_info failed for {link}: {e}")
            return {}

        formats = info.get('formats', [])

        # Collect all available heights
        available_heights = sorted(
            set(f['height'] for f in formats if f.get('height')),
            reverse=True
        )

        quality_map = {}

        for tier_label, tier_max in STANDARD_TIERS:
            # Pick the best height at or below this tier that exists
            matching = [h for h in available_heights if h <= tier_max]
            if not matching:
                continue
            best_height = matching[0]  # highest within this tier

            if tier_label not in quality_map:
                # Find a format at this height to get size info
                candidates = [
                    f for f in formats
                    if f.get('height') == best_height
                    and (f.get('filesize') or f.get('filesize_approx'))
                ]
                size = (candidates[0].get('filesize') or candidates[0].get('filesize_approx')) if candidates else None
                format_selector = f"best[height<={tier_max}]/bestvideo[height<={tier_max}]+bestaudio/best"
                quality_map[tier_label] = (format_selector, fmt_size(size))

        # Audio only option
        auds = [f for f in formats if not f.get('height') and f.get('abr')]
        auds.sort(key=lambda x: (x['abr'], not x.get('protocol', '').startswith('m3u8')), reverse=True)
        if auds:
            best_audio = auds[0]
            label = f"Audio {int(best_audio['abr'])}kbps"
            size = best_audio.get('filesize') or best_audio.get('filesize_approx')
            quality_map[label] = ("bestaudio/best", fmt_size(size))

    return quality_map






# yt_downloader.py
async def download_and_upload(bot, chat_id: int, link: str, format_id: str):
    """Downloads to /tmp, uploads to cache channel via Telethon, forwards to user via Bot API."""
    os.makedirs(TMP_DIR, exist_ok=True)
    outtmpl = os.path.join(TMP_DIR, "%(id)s_%(format_id)s.%(ext)s")

    status_msg = await bot.send_message(chat_id=chat_id, text="⏳ Starting...")
    last_update = time.time()

    async def update_status(text: str):
        nonlocal last_update
        now = time.time()
        if now - last_update >= 3:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=text)
                last_update = now
            except Exception:
                pass

    def dl_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            pct = (downloaded / total * 100) if total else 0
            asyncio.run_coroutine_threadsafe(
                update_status(f"⬇️ Downloading: {pct:.1f}%\nSpeed: {speed/1024/1024:.1f} MB/s"),
                loop
            )

    loop = asyncio.get_event_loop()

    is_audio_only = format_id.startswith("bestaudio")

    ydl_opts = {
        'format': format_id,
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp3' if is_audio_only else 'mp4',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if is_audio_only else [],
        'progress_hooks': [dl_hook],
    }
    _apply_yt_cookies(ydl_opts)

    file_path = None
    try:
        # First extract info to check file size before downloading
        with yt_dlp.YoutubeDL({**ydl_opts, 'skip_download': True}) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(link, download=False))

        size = info.get('filesize') or info.get('filesize_approx') or 0
        if size and size > MAX_DOWNLOAD_SIZE_BYTES:
            size_mb = size / 1024 / 1024
            limit_mb = MAX_DOWNLOAD_SIZE_BYTES / 1024 / 1024
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"❌ File too large ({size_mb:.0f} MB). Limit is {limit_mb:.0f} MB.\nTry a lower quality."
            )
            return

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(link, download=True))
            file_path = ydl.prepare_filename(info)

        if is_audio_only:
            base, _ = os.path.splitext(file_path)
            file_path = f"{base}.mp3"

        if not os.path.exists(file_path):
            await update_status("❌ Download failed.")
            return

        async def ul_callback(sent, total):
            pct = (sent / total * 100) if total else 0
            label = "audio" if is_audio_only else "video"
            await update_status(f"⬆️ Uploading {label}: {pct:.1f}%")

        title = info.get('title', '')
        duration = int(info.get('duration') or 0)

        if is_audio_only:
            attributes = [DocumentAttributeAudio(duration=duration, title=title)]
            caption = f"🎵 {title}\n\nformat: audio"
        else:
            # Try to get video dimensions for proper inline playback
            width = int(info.get('width') or 0)
            height = int(info.get('height') or 0)
            attributes = [DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)]
            caption = f"🎬 {title}\n\nformat: {format_id}"

        # Upload via Telethon (userbot) -> cache channel it's a real member of
        cache_msg = await tg_client.send_file(
            PHANTOM_BOT_CHANNEL_ID,
            file=file_path,
            caption=caption,
            force_document=False,
            attributes=attributes,
            progress_callback=ul_callback,
        )

        # Forward to the user via the BOT, not Telethon
        await bot.forward_message(
            chat_id=chat_id,
            from_chat_id=PHANTOM_BOT_CHANNEL_ID,
            message_id=cache_msg.id,
        )

        done_label = "Audio" if is_audio_only else "Video"
        await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"✅ Done! {done_label} forwarded above.")

    except Exception as e:
        print(f"Failed: {e}")
        await update_status(f"❌ Error: {str(e)[:100]}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)