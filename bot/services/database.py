from config import mdb_client, user_data_path, routine_week_selector_path
import json
import os
import re
from pathlib import Path
from datetime import datetime




db = mdb_client["phantom_bot_db"]
USERS_COLLECTION = "users"


def load_users():
    os.makedirs(".data/", exist_ok=True)
    try:
        data = {}

        for user_data in db[USERS_COLLECTION].find({}):
            roll = user_data.get("roll")
            if roll is None:
                continue

            roll = str(roll)
            data[roll] = {
                "name": user_data.get("name"),
                "section": user_data.get("section"),
                "user_id": user_data.get("user_id"),
                "teacher_choices": user_data.get("teacher_choices", {})
            }

        with open(user_data_path, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error while loading the user data. Error code - {e}")


def get_user_by_roll(roll: str) -> dict | None:
    try:
        return db[USERS_COLLECTION].find_one({"roll": str(roll)})
    except Exception as e:
        print(f"Error while fetching user from '{USERS_COLLECTION}' collection. Error code - {e}")
        return None


def set_user_telegram_id(roll: str, user_id: int) -> bool:
    try:
        result = db[USERS_COLLECTION].update_one(
            {"roll": str(roll)},
            {"$set": {"user_id": user_id}}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"Error while updating user telegram id in '{USERS_COLLECTION}' collection. Error code - {e}")
        return False
        


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
    """
    Upsert a document into `collection`.
    If `data` contains an 'id' key, it is used as the filter so the document
    is replaced in-place instead of duplicated on every call.
    Falls back to plain insert_one for documents without a stable id.
    """
    try:
        col = db[collection]
        if "id" in data:
            col.replace_one({"id": data["id"]}, data, upsert=True)
        else:
            col.insert_one(data)
    except Exception as e:
        print(f"Error while updating the mongodb collection data. Error code - {e}")


def load_data():
    load_teacher_data()
    load_users()
    load_routine_odd_even_sequence()
    load_subject_teachers()
    load_subject_experiments()

def load_teacher_data():
    """Fetch teacher list from live API and cache locally as JSON."""
    import urllib.request
    from config import teacher_data_path, TEACHER_API_URL

    os.makedirs(".data/", exist_ok=True)
    try:
        req = urllib.request.Request(TEACHER_API_URL, headers={"User-Agent": "PhantomBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode())

        teachers = {}
        for t in raw.get("list", []):
            name = t.get("name", "").strip()
            if not name:
                continue
            teachers[name.lower()] = {
                "name": name,
                "post": t.get("post", ""),
                "dept": t.get("dept", "")
            }

        with open(teacher_data_path, "w") as f:
            json.dump(teachers, f, indent=4)
        print(f"Teacher data cached: {len(teachers)} entries → {teacher_data_path}")
    except Exception as e:
        print(f"Error fetching teacher data: {e}")
        # Fallback: keep existing cache if API fails
        if os.path.exists(teacher_data_path):
            print("Using existing cached teacher data.")


# ─── Cover Page history ───────────────────────────────────────────────────────
_coverpage_col = db["coverpage"]


def save_coverpage_record(
    user_id: int,
    roll: str,
    subject: str,
    exp_no: str,
    group: str,              # '1' = 1st 30 of every 60, '2' = 2nd 30
    date_of_experiment: str,
    date_of_submission: str,
) -> None:
    """Persist a generated cover page record for future date hints."""
    try:
        _coverpage_col.insert_one(
            {
                "user_id": user_id,
                "roll": roll,
                "subject": subject,
                "exp_no": str(exp_no),
                "group": str(group),
                "date_of_experiment": date_of_experiment,  # ISO yyyy-mm-dd
                "date_of_submission": date_of_submission,  # ISO yyyy-mm-dd
                "generated_at": datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        print(f"[db] Error saving coverpage record: {e}")


def get_coverpage_dates_by_group(subject: str, exp_no: str) -> dict:
    """
    Return the most recent cover page record for each roll group ('1' and '2')
    for a given subject + experiment number.

    Returns a dict: {"1": record_or_None, "2": record_or_None}
    Used to show '1st 30' / '2nd 30' date hints during the bot flow.
    """
    result = {"1": None, "2": None}
    try:
        for group in ("1", "2"):
            record = _coverpage_col.find_one(
                {"subject": subject, "exp_no": str(exp_no), "group": group},
                sort=[("generated_at", -1)],
            )
            result[group] = record
    except Exception as e:
        print(f"[db] Error fetching coverpage dates by group: {e}")
    return result


# ─── Subject Teachers & Experiments ───────────────────────────────────────────

def load_subject_teachers() -> None:
    """Load subject_teachers from MongoDB and cache to .data/subject_teachers.json."""
    os.makedirs(".data/", exist_ok=True)
    try:
        col = db["subject_teachers"]
        # If collection is empty, seed it from local file
        if col.count_documents({}) == 0:
            local_path = Path(".data/subject_teachers.json")
            if local_path.exists():
                with open(local_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                docs = []
                for key, val in raw_data.items():
                    normalized = re.sub(r"[\s\-]+", "", key).upper()
                    docs.append({
                        "subject": key,
                        "normalized": normalized,
                        "title": val.get("title", ""),
                        "type": val.get("type", "sessional"),
                        "1": val.get("1", {}),
                        "2": val.get("2", {})
                    })
                if docs:
                    col.insert_many(docs)
                    print(f"[db] Seeded subject_teachers with {len(docs)} documents.")

        # Read all documents and write to .data/subject_teachers.json
        data = {}
        for doc in col.find():
            subject = doc["subject"]
            data[subject] = {
                "title": doc.get("title", ""),
                "type": doc.get("type", "sessional"),
                "1": doc.get("1", {}),
                "2": doc.get("2", {})
            }
        with open(".data/subject_teachers.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("[db] Loaded subject_teachers from MongoDB and cached locally.")
    except Exception as e:
        print(f"[db] Error loading subject_teachers: {e}")


def load_subject_experiments() -> None:
    """Load subject_experiments from MongoDB and cache to .data/subject_experiments.json."""
    os.makedirs(".data/", exist_ok=True)
    try:
        col = db["subject_experiments"]
        # If collection is empty, seed it from local file
        if col.count_documents({}) == 0:
            local_path = Path(".data/subject_experiments.json")
            if local_path.exists():
                with open(local_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                docs = []
                for key, val in raw_data.items():
                    if key == "_detail":
                        continue
                    normalized = re.sub(r"[\s\-]+", "", key).upper()
                    experiments = {}
                    for exp_key, exp_val in val.items():
                        if exp_key.isdigit():
                            experiments[str(exp_key)] = exp_val
                    docs.append({
                        "subject": key,
                        "normalized": normalized,
                        "type": val.get("type", "sessional"),
                        "experiments": experiments
                    })
                if docs:
                    col.insert_many(docs)
                    print(f"[db] Seeded subject_experiments with {len(docs)} documents.")

        # Read all documents and write to .data/subject_experiments.json
        data = {}
        for doc in col.find():
            subject = doc["subject"]
            data[subject] = {
                "type": doc.get("type", "sessional"),
                "experiments": doc.get("experiments", {})
            }
        with open(".data/subject_experiments.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print("[db] Loaded subject_experiments from MongoDB and cached locally.")
    except Exception as e:
        print(f"[db] Error loading subject_experiments: {e}")


def get_subject_experiments(subject_name: str) -> dict | None:
    """Get subject experiments from MongoDB using normalized subject name."""
    try:
        normalized = re.sub(r"[\s\-]+", "", subject_name).upper()
        return db["subject_experiments"].find_one({"normalized": normalized})
    except Exception as e:
        print(f"[db] Error fetching subject experiments: {e}")
        return None


def add_experiment_to_subject(subject_name: str, exp_no: str, title: str, exp_type: str) -> None:
    """Add a manual experiment to a subject in MongoDB, if it doesn't already exist."""
    try:
        normalized = re.sub(r"[\s\-]+", "", subject_name).upper()
        doc = db["subject_experiments"].find_one({"normalized": normalized})
        if not doc:
            db["subject_experiments"].insert_one({
                "subject": subject_name,
                "normalized": normalized,
                "type": "sessional" if exp_type == "Lab Report" else "theory",
                "experiments": {
                    str(exp_no): {
                        "type": exp_type,
                        "title": title
                    }
                }
            })
            return

        experiments = doc.get("experiments", {})
        if str(exp_no) not in experiments:
            experiments[str(exp_no)] = {
                "type": exp_type,
                "title": title
            }
            db["subject_experiments"].update_one(
                {"normalized": normalized},
                {"$set": {"experiments": experiments}}
            )
            print(f"[db] Added manual experiment {exp_no} to {subject_name}")
    except Exception as e:
        print(f"[db] Error adding experiment to subject: {e}")
