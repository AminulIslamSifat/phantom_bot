from config import TELETHON_API_HASH, TELETHON_API_ID
from telethon.sessions import StringSession
from telethon import TelegramClient
import os
import json
from config import user_data_path
from config import TEACHER_SUBJECT_PATH
from pathlib import Path


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

teacher_data = _load_json(TEACHER_SUBJECT_PATH)
subjects = {}
for k,v in teacher_data.items():
    subjects[k] = v["type"]
print(subjects)
