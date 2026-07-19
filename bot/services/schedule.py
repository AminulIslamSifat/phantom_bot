import os
import json
from datetime import datetime, date
from config import mdb_client, user_data_path
from telegram import Update
from telegram.ext import ContextTypes

def get_schedule() -> str:
    schedule_db = mdb_client["schedule"]
    
    # We want to fetch schedules from standard collections
    collections = ["ct", "assignment", "semester_final", "backlog"]
    
    db_cols = schedule_db.list_collection_names()
    for col in db_cols:
        if col not in collections and not col.startswith("system."):
            collections.append(col)
            
    schedules = []
    today = date.today()
    
    for col_name in collections:
        col = schedule_db[col_name]
        if col_name == "ct":
            display_type = "CT"
        elif col_name == "assignment":
            display_type = "Assignment"
        elif col_name == "semester_final":
            display_type = "Semester Final"
        elif col_name == "backlog":
            display_type = "Backlog"
        else:
            display_type = col_name.replace("_", " ").title()
            
        docs = list(col.find())
        for doc in docs:
            doc["type"] = display_type
            
            doc_date = doc.get("date", "").strip()
            parsed_date = None
            countdown = ""
            
            if doc_date:
                try:
                    parsed_date = datetime.strptime(doc_date, "%Y-%m-%d").date()
                    delta = (parsed_date - today).days
                    if delta == 0:
                        countdown = " (Today)"
                    elif delta == 1:
                        countdown = " (Tomorrow)"
                    elif delta > 1:
                        countdown = f" ({delta}d left)"
                    elif delta < 0:
                        countdown = f" ({abs(delta)}d ago)"
                except Exception:
                    pass
            
            doc["parsed_date"] = parsed_date
            doc["countdown"] = countdown
            schedules.append(doc)
            
    # Sort chronologically by date
    def sort_key(s):
        d = s["parsed_date"]
        t = s.get("time", "").strip() or ""
        if d is None:
            return (date(9999, 12, 31), t)
        return (d, t)
        
    schedules.sort(key=sort_key)
    
    if not schedules:
        return "✨ No upcoming schedules found!"
        
    lines = ["*RUET CSE Schedule*\n"]
    
    type_emojis = {
        "CT": "🟣",
        "Assignment": "🔵",
        "Semester Final": "🔴",
        "Backlog": "🟡"
    }
    
    for s in schedules:
        emoji = type_emojis.get(s["type"], "📌")
        lines.append(f"{emoji} *{s['type']}: {s['subject']}*")
        
        date_str = s.get('date') or 'TBD'
        time_str = s.get('time') or 'TBD'
        lines.append(f"Date: {date_str}{s['countdown']}\nTime: {time_str}")
        lines.append(f"Teacher: {s.get('teacher', 'N/A')}")
        
        if s.get("topic"):
            lines.append(f"Topic: {s['topic']}")
        if s.get("syllabus"):
            lines.append(f"📖 Syllabus: {s['syllabus']}")
            
        lines.append("───────────────────")
        
    if len(lines) > 1:
        lines.pop()
        
    return "\n".join(lines)


async def circulate_schedule(update: Update, context: ContextTypes) -> None:
    active_users = []
    if os.path.exists(user_data_path):
        try:
            with open(user_data_path, "r") as file:
                user_data = json.load(file)
            for user, data in user_data.items():
                if data.get("user_id") is not None:
                    active_users.append(data["user_id"])
        except Exception as e:
            print(f"Error reading user_data.json: {e}")
            msg = update.message if update.message else update.callback_query.message
            await msg.reply_text("Failed to read user data.")
            return

    if not active_users:
        msg = update.message if update.message else update.callback_query.message
        await msg.reply_text("No active users found to circulate to.")
        return

    try:
        schedule_text = get_schedule()
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        msg = update.message if update.message else update.callback_query.message
        await msg.reply_text("Failed to fetch schedule for circulation.")
        return

    count = 0
    msg = update.message if update.message else update.callback_query.message
    message = await msg.reply_text(f"Please wait...\nThe schedule is being sent to {count} person")

    for user_id in active_users:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=schedule_text,
                parse_mode="Markdown"
            )
            count += 1
            await message.edit_text(f"Please wait...\nThe schedule is being sent to {count} person")
        except Exception as e:
            print(f"Failed to send schedule to {user_id}: {e}")

    await message.edit_text(f"The schedule is circulated to {count} people.")