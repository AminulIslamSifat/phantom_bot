"""
migrate_users.py — One-time migration script.
Reads all per-roll user collections and consolidates them
into a single unified "users" collection.

Does NOT delete old collections. Run once, verify, then clean up manually.

Usage:
    uv run python migrate_users.py
"""

import os
import urllib.parse
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

# ── Connect ───────────────────────────────────────────────────────────────────
username = urllib.parse.quote_plus(os.environ["MONGODB_USERNAME"])
password = urllib.parse.quote_plus(os.environ["MONGODB_USER_PASSWORD"])
client = MongoClient(
    f"mongodb+srv://{username}:{password}@cluster0.5ckeilq.mongodb.net/?appName=Cluster0"
)
db = client["phantom_bot_db"]

TARGET_COLLECTION = "users"
SKIP_NAMES = {"2400000"}  # known non-user numeric collection


def is_user_collection(name: str) -> bool:
    """A user collection is named with a pure integer roll number."""
    if name in SKIP_NAMES:
        return False
    try:
        int(name)
        return True
    except ValueError:
        return False


def migrate() -> None:
    target = db[TARGET_COLLECTION]

    # Create indexes (idempotent)
    target.create_index("roll", unique=True)
    target.create_index("user_id")

    collections = db.list_collection_names()
    user_cols = [c for c in collections if is_user_collection(c)]

    if not user_cols:
        print("No user collections found. Nothing to migrate.")
        return

    migrated = 0
    skipped = 0
    errors = 0

    for roll in sorted(user_cols):
        try:
            doc = db[roll].find_one({"roll": roll})
            if not doc:
                print(f"  [skip] {roll} — no matching document")
                skipped += 1
                continue

            # Build clean user document (drop Mongo _id)
            user_doc = {
                "roll": roll,
                "name": doc.get("name"),
                "section": doc.get("section"),
                "user_id": doc.get("user_id"),
                "teacher_choices": doc.get("teacher_choices", {}),
            }

            # Upsert so re-running the script is safe
            target.update_one(
                {"roll": roll},
                {"$set": user_doc},
                upsert=True,
            )
            migrated += 1
            uname = user_doc.get("name", "?")
            print(f"  [ok]   {roll} → {uname}")

        except Exception as e:
            errors += 1
            print(f"  [err]  {roll} — {e}")

    sep = "=" * 40
    print(f"\n{sep}")
    print(f"Migration complete.")
    print(f"  Migrated : {migrated}")
    print(f"  Skipped  : {skipped}")
    print(f"  Errors   : {errors}")
    print(f"  Target   : db[{TARGET_COLLECTION}] ({target.count_documents({})} docs)")
    print(f"\nOld collections are untouched. Delete them manually when ready.")


if __name__ == "__main__":
    migrate()
    client.close()

