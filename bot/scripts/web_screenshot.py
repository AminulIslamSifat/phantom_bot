import os
import requests
import urllib.parse
from config import (
    SCREENSHOT_API
)

def take_web_screenshot(url, output_path="resources/routine"):
    encoded_url = urllib.parse.quote_plus(url)
    api_url = f"https://shot.screenshotapi.net/screenshot?token={SCREENSHOT_API}&url={encoded_url}&output=image&file_type=png"
    response = requests.get(api_url)

    if response.status_code == 200:
        with open(output_path, "wb") as file:
            file.write(response.content)
        return output_path
    else:
        print(f"API Error - Status: {response.status_code}")
        print(f"Response: {response.text}")
    