import os
import requests
import urllib.parse
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import ssl
from config import (
    SCREENSHOT_API
)

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import ssl


def take_web_screenshot(
    target_url: str,
    output_path: str = "resources/routine.jpg",
) -> str | None:
    api_url = "https://api.screenshotone.com/take"

    for api in SCREENSHOT_API:
        query_params = {
            "access_key": api,
            "url": target_url,
            "format": "jpg",
            "block_ads": "true",
            "block_cookie_banners": "true",
            "block_banners_by_heuristics": "false",
            "block_trackers": "true",
            "delay": "8",
            "timeout": "60",
            "response_type": "by_format",
            "image_quality": "80",
        }

        full_url = f"{api_url}?{urlencode(query_params)}"
        request = Request(full_url)

        ctx = ssl.create_default_context()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with urlopen(request, context=ctx, timeout=70) as response:
                if response.status != 200:
                    print(f"API Error - Status: {response.status}")
                    return None

                image_data = response.read()
                break
        except HTTPError as e:
            print(f"API Error - Status: {e.code}")
            print(f"Response: {e.read().decode(errors='replace')}")

    output_file.write_bytes(image_data)
    return str(output_file)


