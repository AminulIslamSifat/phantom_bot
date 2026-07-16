from config import mdb_client, user_data_path, routine_week_selector_path
import json
import os




db = mdb_client["phantom_bot_db"]


def load_users():
    os.makedirs(".data/", exist_ok=True)
    try:
        collections = db.list_collection_names()
        user_collections = []
        data =  {}

        #Filetering all the additional collections from user
        for x in collections:
            if x == "2400000":
                continue
            try:
                int(x)
                user_collections.append(str(x))
            except:
                continue

        for user in user_collections:
            user_data = db[user].find_one({"roll" : user})

            data[user] = {
                "name": user_data["name"],
                "section": user_data["section"],
                "user_id": user_data["user_id"]
            }
        
        with open(user_data_path, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error while loading the user data. Error code - {e}")
        


def load_routine_odd_even_sequence():
    os.makedirs(".data/", exist_ok=True)
    try:
        routine_collection = db["routine_week_selector"]
        routine_week_data = routine_collection.find_one({"id": "routine_week_selector"})
        data = {
            "id" : routine_week_data["id"],
            "week": routine_week_data["week"]
        }
        with open(routine_week_selector_path, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error while loading routine week data. Error code - {e}")


def update_mongodb_data(collection, data, database=db):
    try:
        col = db[collection]
        col.insert_one(data)
    except Exception as e:
        print(f"Error while updating the mongodb collection data. Error code - {e}")


def load_data():
    load_users()
    load_routine_odd_even_sequence()
