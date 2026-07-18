from config import TELETHON_API_HASH, TELETHON_API_ID
from telethon.sessions import StringSession
from telethon import TelegramClient
import os
import json
from config import user_data_path


# with TelegramClient(StringSession(), TELETHON_API_ID, TELETHON_API_HASH) as client:
#     client.start()  # Enter phone + code
#     print(client.session.save())  # Copy this string

from bot.services.database import db


# collection = db["2400000"]
# data = collection.find_one({"roll": 2400000})
# print(data)

# collection.update_one(
#     {"roll" : 2400000},
#     {"$set" : {"user_id" : "xx"}}
# )

collections = db.list_collection_names()

for col in collections:
    if col != 2400000:
        collection = db[str(col)]
        collection.update_one(
            {"roll" : str(col)},
            {"$set" : {"user_id" : None}}
        )