import os
from dotenv import load_dotenv


load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SCREENSHOT_API = os.environ["SCREENSHOT_API"]
USE_WEBHOOK =  os.environ["USE_WEBHOOK"]
ROUTINE_URL = "https://ruet-cse-c-routine.vercel.app/"
CANCEL_BUTTON = "❌ Cancel"