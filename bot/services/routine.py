import os
import requests
import urllib.parse
from datetime import date, timedelta
from config import (
    ROUTINE_URL_ODD_WEEK,
    ROUTINE_URL_EVEN_WEEK,
    routine_path_odd_week,
    routine_path_even_week
)
from bot.scripts.web_screenshot import take_web_screenshot

    
def update_routine():
    try:
        print("Routine Update started...")
        os.makedirs("resources/routine", exist_ok=True)
        take_web_screenshot(ROUTINE_URL_ODD_WEEK, output_path=routine_path_odd_week)
        take_web_screenshot(ROUTINE_URL_EVEN_WEEK, output_path=routine_path_even_week)
        print("Routine Updated.")
    except Exception as e:
        print(f"Something went wrong while updating the routine. Error Code - {e}")


def is_even_week():
    calibration_dates = {"date1": date(2026, 7, 9), "date2": date(2026, 7, 2)}
    calibration_date = calibration_dates["date1"]
    today = date.today()
    day_count = (today - calibration_date).days
    activation_date = today - timedelta(day_count % 7 - 2)
    is_even = (day_count // 7) % 2 == 0
    return (is_even, str(activation_date))
