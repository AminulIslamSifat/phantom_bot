import os
import requests
from config import ROUTINE_URL, SCREENSHOT_API

def take_web_screenshot(url, output_path="resources/routine"):
    response = requests.get(f"https://api.screenshotapi.net/screenshot?token={SCREENSHOT_API}&url={url}&full_page=true&output=image")

    if response.status_code == 200:
        with open(output_path, "wb") as file:
            file.write(response.content)
        return output_path

take_web_screenshot(ROUTINE_URL)