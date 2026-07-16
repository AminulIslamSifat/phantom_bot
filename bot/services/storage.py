import json
import time
from config import routine_week_selector_path, user_data_path

def get_user_data():
    with open(user_data_path, "r") as file:
        return json.load(file)

def get_routine_week():
    with open(routine_week_selector_path, "r") as file:
        return json.load(file)["week"]
    