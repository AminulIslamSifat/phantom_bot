
"""
Flask web admin panel — migrated from ruet-cse.
All original logic preserved; adapted for phantom_bot monorepo structure.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
from pathlib import Path
from urllib.parse import quote_plus
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from bson.objectid import ObjectId
import bson
from datetime import datetime, date, timezone, timedelta
import re
from concurrent.futures import ThreadPoolExecutor


class _PrefixMiddleware:
    """WSGI middleware that strips a URL prefix so Flask sees clean paths
    while generating URLs with the prefix intact."""

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        script_name = environ.get("SCRIPT_NAME", "")
        path_info = environ.get("PATH_INFO", "")
        # Strip prefix from PATH_INFO so Flask routes match
        if path_info.startswith(self.prefix):
            environ["PATH_INFO"] = path_info[len(self.prefix):] or "/"
        environ["SCRIPT_NAME"] = script_name + self.prefix
        return self.app(environ, start_response)


BASE_DIR = Path(__file__).parent

# ── MongoDB ────────────────────────────────────────────────────────────────
MONGODB_USERNAME     = os.environ.get("MONGODB_USERNAME", "")
MONGODB_USER_PASSWORD = os.environ.get("MONGODB_USER_PASSWORD", "")

client       = MongoClient(f"mongodb+srv://{quote_plus(MONGODB_USERNAME)}:{quote_plus(MONGODB_USER_PASSWORD)}@cluster0.5ckeilq.mongodb.net/?appName=Cluster0")
schedule_db  = client["schedule"]
phantom_db   = client["phantom_bot_db"]

# ── Admin Auth ────────────────────────────────────────────────────────────
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

SCHEDULE_TYPES = ["CT", "Assignment", "Semester Final", "Backlog"]

_home_stats_cache = {"data": None, "expires_at": None}


def clear_home_stats_cache():
    _home_stats_cache["data"] = None


def get_collection(schedule_type: str):
    return schedule_db[schedule_type.lower().replace(" ", "_")]


def normalize(key: str) -> str:
    return re.sub(r"[\s\-]+", "", key).upper()


def _routine_path(week: str) -> Path:
    return BASE_DIR / f"routine_{week}_week.json"


def _load_routine(week: str) -> dict:
    try:
        doc = phantom_db["routine"].find_one({"_id": f"{week}_week"})
        if doc:
            doc.pop("_id", None)
            doc.pop("updated_at", None)
            doc.pop("week", None)
            return doc
    except Exception as e:
        print(f"[_load_routine] MongoDB fetch error: {e}")

    p = _routine_path(week)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"periods": [], "times": [], "routine": []}


def create_app(url_prefix: str = "") -> Flask:
    """Factory function to create the Flask web admin app.

    Args:
        url_prefix: Set to "/panel" when running behind a reverse proxy
                    so Flask generates correct static/template URLs.
    """
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    if url_prefix:
        app.wsgi_app = _PrefixMiddleware(app.wsgi_app, url_prefix)
        # Rewrite absolute href/action paths so they include the prefix.
        # <base> doesn't fix absolute paths like href="/" — only relative ones.
        import re as _re
        _abs_attr = _re.compile(r'((?:href|action|src)\s*=\s*")(/(?!/))')

        @app.after_request
        def _rewrite_paths(response):
            if response.content_type and "text/html" in response.content_type:
                data = response.get_data(as_text=True)
                data = _abs_attr.sub(rf'\1{url_prefix}\2', data)
                response.set_data(data)
            return response
    app.secret_key = os.environ.get("SECRET_KEY", "ruet-cse-change-this-secret")
    if url_prefix:
        app.config["APPLICATION_ROOT"] = url_prefix
        app.config["SESSION_COOKIE_PATH"] = url_prefix

    # ────────────────────────────────────────────────────────────────────────
    # Homepage
    # ────────────────────────────────────────────────────────────────────────

    @app.route("/")
    def home():
        now = datetime.now(timezone.utc)
        if _home_stats_cache["data"] is not None and _home_stats_cache["expires_at"] > now:
            cached = _home_stats_cache["data"]
            return render_template("index.html",
                schedule_count=cached["schedule_count"],
                teachers_count=cached["teachers_count"],
                experiments_count=cached["experiments_count"],
            )

        def get_count(coll_name_or_type, is_phantom=False):
            coll = phantom_db[coll_name_or_type] if is_phantom else get_collection(coll_name_or_type)
            try:
                return coll.estimated_document_count()
            except Exception:
                return coll.count_documents({})

        jobs = [(t, False) for t in SCHEDULE_TYPES] + [("subject_teachers", True), ("subject_experiments", True)]
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda args: get_count(*args), jobs))

        schedule_count = sum(results[:4])
        teachers_count = results[4]
        experiments_count = results[5]

        cached_data = {
            "schedule_count": schedule_count,
            "teachers_count": teachers_count,
            "experiments_count": experiments_count
        }
        _home_stats_cache["data"] = cached_data
        _home_stats_cache["expires_at"] = now + timedelta(seconds=60)

        return render_template("index.html",
            schedule_count=schedule_count,
            teachers_count=teachers_count,
            experiments_count=experiments_count,
        )

    # ────────────────────────────────────────────────────────────────────────
    # Routine — display & data API
    # ────────────────────────────────────────────────────────────────────────

    @app.route("/routine/<week>")
    def routine_display(week):
        if week not in ("odd", "even"):
            return "Not found", 404
        data = _load_routine(week)
        return render_template("routine_display.html", week=week, data=data)

    @app.route("/routine/data/<week>.json")
    def routine_data(week):
        if week not in ("odd", "even"):
            return jsonify({"error": "Not found"}), 404
        return jsonify(_load_routine(week))

    @app.route("/routine/editor")
    def routine_editor():
        return render_template("routine_editor.html")

    @app.route("/routine/save", methods=["POST"])
    def routine_save():
        payload = request.get_json(silent=True) or {}
        week = payload.get("week")
        data = payload.get("data")

        if week not in ("odd", "even") or not data:
            return jsonify({"error": "Invalid payload"}), 400

        try:
            _routine_path(week).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            phantom_db["routine"].update_one(
                {"_id": f"{week}_week"},
                {"$set": {**data, "week": week, "updated_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ────────────────────────────────────────────────────────────────────────
    # Schedule CRUD
    # ────────────────────────────────────────────────────────────────────────

    @app.route("/schedule")
    def schedule_index():
        docs = {}
        for stype in SCHEDULE_TYPES:
            coll = get_collection(stype)
            docs[stype] = list(coll.find().sort("date", -1))
            for d in docs[stype]:
                d["_id"] = str(d["_id"])
        return render_template("schedule_index.html", schedule_types=SCHEDULE_TYPES, docs=docs)

    @app.route("/schedule/add/<stype>", methods=["POST"])
    def schedule_add(stype):
        if stype not in SCHEDULE_TYPES:
            return "Invalid type", 400
        subject = request.form.get("subject", "").strip()
        date_str = request.form.get("date", "").strip()
        note = request.form.get("note", "").strip()
        if not subject or not date_str:
            return "Subject and date required", 400
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return "Invalid date format", 400
        get_collection(stype).insert_one({"subject": subject, "date": dt, "note": note})
        clear_home_stats_cache()
        return redirect(url_for("schedule_index"))

    @app.route("/schedule/edit/<stype>/<oid>", methods=["GET", "POST"])
    def schedule_edit(stype, oid):
        if stype not in SCHEDULE_TYPES:
            return "Invalid type", 400
        try:
            oid_obj = ObjectId(oid)
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        coll = get_collection(stype)
        doc = coll.find_one({"_id": oid_obj})
        if not doc:
            return "Not found", 404
        if request.method == "POST":
            subject = request.form.get("subject", "").strip()
            date_str = request.form.get("date", "").strip()
            note = request.form.get("note", "").strip()
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return "Invalid date format", 400
            coll.update_one({"_id": oid_obj}, {"$set": {"subject": subject, "date": dt, "note": note}})
            clear_home_stats_cache()
            return redirect(url_for("schedule_index"))
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("date"), (date, datetime)):
            doc["date"] = doc["date"].strftime("%Y-%m-%d")
        return render_template("schedule_edit.html", stype=stype, doc=doc)

    @app.route("/schedule/delete/<stype>/<oid>", methods=["POST"])
    def schedule_delete(stype, oid):
        if stype not in SCHEDULE_TYPES:
            return "Invalid type", 400
        try:
            get_collection(stype).delete_one({"_id": ObjectId(oid)})
            clear_home_stats_cache()
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        return redirect(url_for("schedule_index"))

    # ────────────────────────────────────────────────────────────────────────
    # Experiments CRUD
    # ────────────────────────────────────────────────────────────────────────

    @app.route("/experiments")
    def experiments():
        docs = list(phantom_db["subject_experiments"].find())
        for d in docs:
            d["_id"] = str(d["_id"])
        return render_template("experiments.html", subjects=docs)

    @app.route("/experiments/add", methods=["POST"])
    def add_experiment_subject():
        subject = request.form.get("subject", "").strip()
        if not subject:
            return "Subject name is required", 400
        norm = normalize(subject)
        if not phantom_db["subject_experiments"].find_one({"normalized": norm}):
            phantom_db["subject_experiments"].insert_one({
                "subject": subject, "normalized": norm, "experiments": {}
            })
            clear_home_stats_cache()
        return redirect(url_for("experiments"))

    @app.route("/experiments/edit/<oid>", methods=["GET", "POST"])
    def edit_experiment_subject(oid):
        try:
            oid_obj = ObjectId(oid)
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        doc = phantom_db["subject_experiments"].find_one({"_id": oid_obj})
        if not doc:
            return "Not found", 404
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add_exp":
                exp_no = request.form.get("exp_no", "").strip()
                exp_title = request.form.get("exp_title", "").strip()
                if exp_no and exp_title:
                    experiments_data = doc.get("experiments", {})
                    experiments_data[exp_no] = exp_title
                    phantom_db["subject_experiments"].update_one({"_id": oid_obj},
                        {"$set": {"experiments": experiments_data}})
            elif action == "delete_exp":
                exp_no = request.form.get("exp_no", "").strip()
                if exp_no:
                    experiments_data = doc.get("experiments", {})
                    if exp_no in experiments_data:
                        del experiments_data[exp_no]
                        phantom_db["subject_experiments"].update_one({"_id": oid_obj},
                            {"$set": {"experiments": experiments_data}})
            return redirect(url_for("edit_experiment_subject", oid=oid))
        doc["_id"] = str(doc["_id"])
        experiments_sorted = dict(sorted(
            doc.get("experiments", {}).items(),
            key=lambda x: int(x[0]) if x[0].isdigit() else 9999
        ))
        return render_template("edit_experiment.html", subject=doc, experiments=experiments_sorted)

    @app.route("/experiments/delete/<oid>", methods=["POST"])
    def delete_experiment_subject(oid):
        try:
            phantom_db["subject_experiments"].delete_one({"_id": ObjectId(oid)})
            clear_home_stats_cache()
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        return redirect(url_for("experiments"))

    # ────────────────────────────────────────────────────────────────────────
    # Subject Teachers CRUD
    # ────────────────────────────────────────────────────────────────────────

    @app.route("/teachers")
    def teachers():
        docs = list(phantom_db["subject_teachers"].find())
        for d in docs:
            d["_id"] = str(d["_id"])
        return render_template("teachers.html", subjects=docs)

    @app.route("/teachers/add", methods=["POST"])
    def add_teacher_subject():
        subject = request.form.get("subject", "").strip()
        title   = request.form.get("title", "").strip()
        stype   = request.form.get("type", "sessional").strip()
        if not subject:
            return "Subject name is required", 400
        norm = normalize(subject)
        if not phantom_db["subject_teachers"].find_one({"normalized": norm}):
            phantom_db["subject_teachers"].insert_one({
                "subject": subject, "normalized": norm, "title": title,
                "type": stype, "1": {}, "2": {}
            })
            clear_home_stats_cache()
        return redirect(url_for("teachers"))

    @app.route("/teachers/edit/<oid>", methods=["GET", "POST"])
    def edit_teacher_subject(oid):
        try:
            oid_obj = ObjectId(oid)
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        doc = phantom_db["subject_teachers"].find_one({"_id": oid_obj})
        if not doc:
            return "Not found", 404
        if request.method == "POST":
            action = request.form.get("action")
            if action == "update_meta":
                phantom_db["subject_teachers"].update_one({"_id": oid_obj}, {"$set": {
                    "title": request.form.get("title", "").strip(),
                    "type":  request.form.get("type", "sessional"),
                }})
            elif action == "update_teacher":
                key = request.form.get("key", "1")
                if key in ("1", "2"):
                    phantom_db["subject_teachers"].update_one({"_id": oid_obj}, {"$set": {key: {
                        "name":        request.form.get("name", "").strip(),
                        "designation": request.form.get("designation", "").strip(),
                        "department":  request.form.get("department", "").strip(),
                        "dept_short":  request.form.get("dept_short", "").strip(),
                    }}})
            return redirect(url_for("edit_teacher_subject", oid=oid))
        doc["_id"] = str(doc["_id"])
        return render_template("edit_teacher.html", subject=doc)

    @app.route("/teachers/delete/<oid>", methods=["POST"])
    def delete_teacher_subject(oid):
        try:
            phantom_db["subject_teachers"].delete_one({"_id": ObjectId(oid)})
            clear_home_stats_cache()
        except bson.errors.InvalidId:
            return "Invalid ID", 404
        return redirect(url_for("teachers"))

    # ────────────────────────────────────────────────────────────────────────
    # Admin Panel — user management
    # ────────────────────────────────────────────────────────────────────────

    def load_users():
        """Load all active users from the unified phantom_bot_db.users collection."""
        try:
            def fetch_admins():
                return list(phantom_db["admin"].find())
            def fetch_users():
                return list(phantom_db["users"].find({}))

            with ThreadPoolExecutor(max_workers=2) as executor:
                fut_admins = executor.submit(fetch_admins)
                fut_users = executor.submit(fetch_users)
                admins_docs = fut_admins.result()
                users_docs = fut_users.result()

            admin_rolls = {
                str(doc["roll"])
                for doc in admins_docs
                if doc.get("roll") is not None
            }

            users = []
            for user_data in users_docs:
                roll = user_data.get("roll")
                if roll is None:
                    continue
                roll = str(roll)
                if not user_data.get("user_id"):
                    continue
                users.append({
                    "roll": roll,
                    "name": user_data.get("name", "Unknown"),
                    "is_admin": roll in admin_rolls,
                })

            users.sort(key=lambda u: u["roll"])
            return users
        except Exception as e:
            print(f"[load_users] Error: {e}")
            return []

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session["admin_logged_in"] = True
                return redirect(url_for("admin_panel"))
            return render_template("admin_login.html", error="Invalid credentials")
        return render_template("admin_login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_logged_in", None)
        return redirect(url_for("home"))

    @app.route("/admin")
    def admin_panel():
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return render_template("admin_panel.html")

    @app.route("/admin/api/users")
    def admin_api_users():
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(load_users())

    @app.route("/admin/promote", methods=["POST"])
    def admin_promote():
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        roll = data.get("roll", "").strip()
        user_id = data.get("user_id", "").strip()
        if not roll:
            return jsonify({"error": "Roll required"}), 400
        phantom_db["admin"].update_one(
            {"roll": roll},
            {"$set": {"roll": roll, "user_id": user_id, "promoted_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return jsonify({"ok": True, "roll": roll, "status": "admin"})

    @app.route("/admin/demote", methods=["POST"])
    def admin_demote():
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        roll = data.get("roll", "").strip()
        if not roll:
            return jsonify({"error": "Roll required"}), 400
        phantom_db["admin"].delete_one({"roll": roll})
        return jsonify({"ok": True, "roll": roll, "status": "user"})

    return app
