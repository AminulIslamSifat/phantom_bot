from config import TELETHON_API_HASH, TELETHON_API_ID
from telethon.sessions import StringSession
from telethon import TelegramClient


with TelegramClient(StringSession(), TELETHON_API_ID, TELETHON_API_HASH) as client:
    client.start()  # Enter phone + code
    print(client.session.save())  # Copy this string