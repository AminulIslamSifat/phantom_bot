import os
import asyncio
import json
import threading
import time
from datetime import date, datetime, timedelta
from config import (
    ROUTINE_URL_ODD_WEEK,
    ROUTINE_URL_EVEN_WEEK,
    routine_path_odd_week,
    routine_path_even_week,
    routine_week_selector_path,
    user_data_path
)
from bot.scripts.web_screenshot import take_web_screenshot
from bot.services.storage import get_routine_week
from bot.services.database import update_mongodb_data, db
from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup


ROUTINE_SYNC_STATE_PATH = ".data/routine_last_sync.json"

_routine_update_lock = threading.Lock()
_routine_update_in_progress = False
_routine_timer_lock = threading.Lock()
_routine_update_timer: threading.Timer | None = None


def _utc_now() -> datetime:
    return datetime.utcnow()


def _latest_routine_updated_at() -> datetime | None:
    try:
        latest: datetime | None = None
        for doc in db["routine"].find({}, {"updated_at": 1}):
            updated_at = doc.get("updated_at")
            if isinstance(updated_at, datetime) and (latest is None or updated_at > latest):
                latest = updated_at
        return latest
    except Exception as e:
        print(f"Could not read routine updated_at from MongoDB. Error Code - {e}")
        return None


def _load_last_sync_time() -> datetime | None:
    try:
        if not os.path.exists(ROUTINE_SYNC_STATE_PATH):
            return None
        with open(ROUTINE_SYNC_STATE_PATH, "r") as file:
            raw = json.load(file).get("last_sync")
        return datetime.fromisoformat(raw) if raw else None
    except Exception as e:
        print(f"Could not read routine sync state. Error Code - {e}")
        return None


def _save_last_sync_time(timestamp: datetime | None) -> None:
    try:
        os.makedirs(".data/", exist_ok=True)
        with open(ROUTINE_SYNC_STATE_PATH, "w") as file:
            json.dump({"last_sync": timestamp.isoformat() if timestamp else None}, file, indent=4)
    except Exception as e:
        print(f"Could not save routine sync state. Error Code - {e}")


def update_routine() -> None:
    global _routine_update_in_progress

    with _routine_update_lock:
        if _routine_update_in_progress:
            print("Routine update already running. Skipping this request.")
            return
        _routine_update_in_progress = True

    try:
        print("Routine Update started...")
        os.makedirs("resources/routine", exist_ok=True)
        take_web_screenshot(ROUTINE_URL_ODD_WEEK, output_path=routine_path_odd_week)
        take_web_screenshot(ROUTINE_URL_EVEN_WEEK, output_path=routine_path_even_week)
        _save_last_sync_time(_latest_routine_updated_at() or _utc_now())
        print("Routine Updated.")
    except Exception as e:
        print(f"Something went wrong while updating the routine. Error Code - {e}")
    finally:
        with _routine_update_lock:
            _routine_update_in_progress = False


def _schedule_routine_update() -> None:
    global _routine_update_timer

    with _routine_timer_lock:
        if _routine_update_timer is not None:
            _routine_update_timer.cancel()
        _routine_update_timer = threading.Timer(3.0, update_routine)
        _routine_update_timer.daemon = True
        _routine_update_timer.start()


def sync_routine_if_stale() -> None:
    try:
        missing_images = not (
            os.path.exists(routine_path_odd_week) and os.path.exists(routine_path_even_week)
        )
        last_sync = _load_last_sync_time()

        if missing_images or last_sync is None:
            update_routine()
            return

        latest_update = _latest_routine_updated_at()
        if latest_update is not None and latest_update > last_sync:
            update_routine()
    except Exception as e:
        print(f"Something went wrong while syncing the routine on startup. Error Code - {e}")


def start_routine_watcher() -> None:
    def _watch_routine_collection() -> None:
        sync_routine_if_stale()

        pipeline = [{"$match": {"ns.coll": "routine"}}]
        resume_token = None

        while True:
            try:
                watch_kwargs = {"resume_after": resume_token} if resume_token else {}
                with db.watch(pipeline, **watch_kwargs) as stream:
                    print("Routine MongoDB watcher started...")
                    for change in stream:
                        resume_token = stream.resume_token
                        operation_type = change.get("operationType", "unknown")
                        print(f"Routine data changed ({operation_type}). Scheduling routine image update...")
                        _schedule_routine_update()
            except Exception as e:
                print(f"Routine watcher error. Error Code - {e}. Restarting in 10 seconds...")
                time.sleep(10)
                resume_token = None
                sync_routine_if_stale()

    watcher = threading.Thread(target=_watch_routine_collection, daemon=True)
    watcher.start()


def is_even_week():
    week = get_routine_week()
    calibration_dates = {"date1": date(2026, 7, 9), "date2": date(2026, 7, 2)}
    calibration_date = calibration_dates["date1"] if week=="even" else calibration_dates["date2"]
    today = date.today()
    day_count = (today - calibration_date).days
    activation_date = today - timedelta(day_count % 7 - 2)
    is_even = (day_count // 7) % 2 == 0
    return (is_even, str(activation_date))


def toggle_routine():
    week = get_routine_week()
    toggled_week = "even" if week=="odd" else "odd"
    data = {
        "id" : "routine_week_selector",
        "week": toggled_week
    }
    with open(routine_week_selector_path, "w") as file:
        json.dump(data, file, indent=4)
    update_mongodb_data("routine_week_selector", data)
    print("Routine toggled successfully")


async def circulate_routine(update: Update, context: ContextTypes) -> None:
    if not os.path.exists(user_data_path):
        return await update.effective_message.reply_text("No user data found.")

    with open(user_data_path, "r") as file:
        user_data = json.load(file)

    active_users = [
        data["user_id"] for data in user_data.values()
        if data["user_id"] is not None
    ]

    is_even, starting_date = is_even_week()
    routine_path = routine_path_even_week if is_even else routine_path_odd_week
    path_extension = "routine-even-week" if is_even else "routine-odd-week"

    routine_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Live Routine", url=f"https://ruet-cse-liart.vercel.app/routine/{path_extension}/")]
    ])

    msg = await update.effective_message.reply_text(
        f"Sending routine to {len(active_users)} people..."
    )

    async def send_one(user_id: int) -> bool:
        try:
            await context.bot.send_photo(
                chat_id=int(user_id),
                photo=routine_path,
                caption=f"This routine is applicable from {starting_date}.",
                reply_markup=routine_keyboard,
            )
            return True
        except Exception as e:
            print(f"Error sending to {user_id}: {e}")
            return False

    results = await asyncio.gather(*(send_one(uid) for uid in active_users))
    success_count = sum(results)

    await msg.edit_text(f"Routine circulated to {success_count}/{len(active_users)} people. ✅")
