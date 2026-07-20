from config import TELETHON_API_HASH, TELETHON_API_ID
from telethon.sessions import StringSession
from telethon import TelegramClient
import os
import json
from config import user_data_path
from config import TEACHER_SUBJECT_PATH
from pathlib import Path

from config import mdb_client

db = mdb_client["phantom_bot_db"]

collections = db.list_collection_names()

print(collections)