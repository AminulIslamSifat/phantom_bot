from config import mdb_client, user_data_path, routine_week_selector_path
import json
import os
import re
from pathlib import Path
from datetime import datetime




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
    load_teacher_data()
    load_users()
    load_routine_odd_even_sequence()
    sync_subject_details()

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


# ─── Subject Details cache ───────────────────────────────────────────────────

def sync_subject_details() -> None:
    """Sync coverpage/config/subject_detail.json to MongoDB subject_detail collection."""
    try:
        base_dir = Path(__file__).parent.parent.parent
        json_path = base_dir / "coverpage" / "config" / "subject_detail.json"
        if not json_path.exists():
            print(f"[db] subject_detail.json not found at {json_path}")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        col = db["subject_detail"]
        for key, val in raw_data.items():
            if key == "_detail":
                continue

            normalized = re.sub(r"[\s\-]+", "", key).upper()
            subject_type = val.get("type", "sessional")

            # Parse experiments (all keys that are digit keys)
            experiments = {}
            for exp_key, exp_val in val.items():
                if exp_key.isdigit():
                    experiments[str(exp_key)] = exp_val

            existing = col.find_one({"normalized": normalized})
            if not existing:
                col.insert_one({
                    "subject": key,
                    "normalized": normalized,
                    "type": subject_type,
                    "experiments": experiments
                })
            else:
                db_exps = existing.get("experiments", {})
                # local JSON initial files merge with DB
                updated_exps = {**experiments, **db_exps}
                col.update_one(
                    {"normalized": normalized},
                    {"$set": {"type": subject_type, "experiments": updated_exps}}
                )
        print("[db] Subject details cache synced.")
    except Exception as e:
        print(f"[db] Error syncing subject details: {e}")


def get_subject_detail(subject_name: str) -> dict | None:
    """Get subject detail from MongoDB using normalized subject name."""
    try:
        normalized = re.sub(r"[\s\-]+", "", subject_name).upper()
        return db["subject_detail"].find_one({"normalized": normalized})
    except Exception as e:
        print(f"[db] Error fetching subject detail: {e}")
        return None


def add_experiment_to_subject(subject_name: str, exp_no: str, title: str, exp_type: str) -> None:
    """Add a manual experiment to a subject in MongoDB, if it doesn't already exist."""
    try:
        normalized = re.sub(r"[\s\-]+", "", subject_name).upper()
        doc = db["subject_detail"].find_one({"normalized": normalized})
        if not doc:
            db["subject_detail"].insert_one({
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
            db["subject_detail"].update_one(
                {"normalized": normalized},
                {"$set": {"experiments": experiments}}
            )
            print(f"[db] Added manual experiment {exp_no} to {subject_name}")
    except Exception as e:
        print(f"[db] Error adding experiment to subject: {e}")

