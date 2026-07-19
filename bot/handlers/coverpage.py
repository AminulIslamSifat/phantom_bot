"""
Cover Page Conversation Handler
================================
Flow:
  "Cover Page" message
    → SELECT_SUBJECT   : show subject buttons
    → SELECT_EXPERIMENT: show experiment buttons or ask manual input
    → MANUAL_EXP_INPUT : receive typed "exp_no : exp_title"
    → ENTER_DATES      : ask for "dd-mm-yyyy, dd-mm-yyyy"

Every step shows [Official] [Cancel] side by side at the bottom.
"""

import json
import os
import re
import asyncio
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import user_data_path
from bot.services.database import (
    save_coverpage_record, 
    get_subject_experiments, 
    add_experiment_to_subject,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent.parent  # project root
TEACHER_SUBJECT_PATH = _BASE / ".data" / "subject_teachers.json"
COVERPAGE_OUTPUT_DIR = _BASE / "coverpage" / "generated_covers"
OFFICIAL_URL = "https://ruet-cover-page.github.io/"

# ─── Conversation states ───────────────────────────────────────────────────────
SELECT_SUBJECT    = "cp_select_subject"
SELECT_TEACHER    = "cp_select_teacher"
SELECT_EXPERIMENT = "cp_select_experiment"
MANUAL_EXP_INPUT  = "cp_manual_exp_input"
ENTER_DATES       = "cp_enter_dates"

# ─── Persistent footer keyboard ───────────────────────────────────────────────
def _footer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Official", url=OFFICIAL_URL),
            InlineKeyboardButton("Cancel",   callback_data="coverpage:cancel"),
        ]
    ])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_subject(key: str) -> str:
    """'EEE - 2152' or 'EEE 2152' → 'EEE2152' for fuzzy matching."""
    return re.sub(r"[\s\-]+", "", key).upper()





def _get_student_by_user_id(user_id: int) -> tuple[str, dict] | tuple[None, None]:
    """Return (roll, student_data_dict) or (None, None) if not found."""
    if not os.path.exists(user_data_path):
        return None, None
    with open(user_data_path, "r") as f:
        user_data = json.load(f)
    for roll, data in user_data.items():
        if str(data.get("user_id")) == str(user_id):
            return roll, data
    return None, None


def _get_student_group(roll: str) -> str:
    """
    Determine which teacher group a student belongs to based on roll number.
    Pattern repeats every 60 students:
      001-030, 061-090, 121-150  →  '1'  (1st 30)
      031-060, 091-120, 151-180  →  '2'  (2nd 30)
    """
    try:
        suffix = int(roll[-3:])          # last 3 digits
        pos    = (suffix - 1) % 60       # 0-indexed position within 60-cycle
        return "1" if pos < 30 else "2"
    except (ValueError, IndexError):
        return "1"                        # safe default


def _get_teacher(subject: str, roll: str, teacher_key: str = None) -> dict:
    """
    Return teacher dict for a subject. If teacher_key is provided, use it directly.
    Otherwise, fall back to student's roll group.
    """
    teacher_data = _load_json(TEACHER_SUBJECT_PATH)
    teachers_for_subject = teacher_data.get(subject, {})
    if not teacher_key:
        teacher_key = _get_student_group(roll)
    return teachers_for_subject.get(teacher_key) or teachers_for_subject.get("1", {})


def _parse_date(raw: str) -> str | None:
    """
    Accept dd-mm-yyyy or dd/mm/yyyy (with optional surrounding spaces).
    Returns ISO yyyy-mm-dd or None on failure.
    """
    raw = raw.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_dates_input(text: str) -> tuple[str | None, str | None]:
    """
    Parse "dd-mm-yyyy, dd-mm-yyyy" or "dd/mm/yyyy , dd/mm/yyyy".
    Returns (exp_date_iso, sub_date_iso) or (None, None) on failure.
    """
    # Split on comma with optional surrounding whitespace
    parts = re.split(r"\s*,\s*", text.strip())
    if len(parts) != 2:
        return None, None
    exp_date = _parse_date(parts[0])
    sub_date = _parse_date(parts[1])
    return exp_date, sub_date


def _display_date(iso: str) -> str:
    """'2026-07-19' → '19-07-2026'"""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return iso


def _build_subject_keyboard(subjects: list[str]) -> InlineKeyboardMarkup:
    """2 subjects per row, then footer."""
    rows = []
    for i in range(0, len(subjects), 2):
        chunk = subjects[i : i + 2]
        rows.append([
            InlineKeyboardButton(s, callback_data=f"coverpage:subject:{s}")
            for s in chunk
        ])
    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel",   callback_data="coverpage:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _build_experiment_keyboard(experiments: dict) -> InlineKeyboardMarkup:
    """
    One experiment per row showing 'Exp N: Title', plus a manual entry row, then footer.
    experiments: {exp_no: {type, title}, ...}
    """
    rows = []
    for exp_no, detail in experiments.items():
        title = detail.get("title", "")
        label = f"Exp {exp_no}: {title[:40]}{'…' if len(title) > 40 else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"coverpage:exp:{exp_no}")])
    rows.append([InlineKeyboardButton("✏️ Enter Manually", callback_data="coverpage:exp:manual")])
    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel",   callback_data="coverpage:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


# ─── Entry point ──────────────────────────────────────────────────────────────

async def cover_page_start(update: Update, context: ContextTypes) -> str:
    """Entry: triggered by the 'Cover Page' reply keyboard button."""
    context.user_data.clear()  # fresh session each time

    teacher_data = _load_json(TEACHER_SUBJECT_PATH)
    subjects = [k for k in teacher_data.keys()]

    await update.message.reply_text(
        "📄 *Cover Page Generator*\n\nSelect your subject:",
        parse_mode="Markdown",
        reply_markup=_build_subject_keyboard(subjects),
    )
    return SELECT_SUBJECT


# ─── Step 1 : Subject selected ────────────────────────────────────────────────

async def _transition_to_experiment_step(query, context: ContextTypes, subject: str) -> str:
    # Load experiment data from MongoDB
    subject_doc = get_subject_experiments(subject)
    experiments = {}
    
    # We also check the subject type from subject_teachers.json to be consistent
    subject_teachers = _load_json(TEACHER_SUBJECT_PATH)
    subject_info = subject_teachers.get(subject, {})
    subject_type = subject_info.get("type", "sessional")
    
    if subject_doc:
        experiments = subject_doc.get("experiments", {})
        # If type isn't in subject_experiments, use type from subject_teachers
        subject_type = subject_doc.get("type", subject_type)

    context.user_data["cp_subject_type"] = subject_type
    context.user_data["cp_experiments"] = experiments

    if experiments:
        await query.edit_message_text(
            f"📘 *{subject}*\n\nSelect an experiment or enter manually:",
            parse_mode="Markdown",
            reply_markup=_build_experiment_keyboard(experiments),
        )
        return SELECT_EXPERIMENT
    else:
        # No experiment data — skip straight to manual input
        exp_label = "assignment" if subject_type == "theory" else "experiment"
        await query.edit_message_text(
            f"📘 *{subject}*\n\n"
            f"No {exp_label} list found for this subject.\n"
            f"Please type the {exp_label} details in this format:\n\n"
            f"`exp_no : Title`",
            parse_mode="Markdown",
            reply_markup=_footer_keyboard(),
        )
        return MANUAL_EXP_INPUT


async def cp_subject_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    subject = query.data.removeprefix("coverpage:subject:")
    context.user_data["cp_subject"] = subject

    # Get student info to check saved choice
    roll, student = _get_student_by_user_id(query.from_user.id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /start.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    # Load subject info
    subject_teachers = _load_json(TEACHER_SUBJECT_PATH)
    subject_info = subject_teachers.get(subject, {})
    subject_type = subject_info.get("type", "sessional")
    context.user_data["cp_subject_type"] = subject_type

    # Check for saved teacher choice
    teacher_choices = student.get("teacher_choices", {})
    saved_teacher_key = teacher_choices.get(subject)
    
    # Prompt user to select teacher
    t1_name = subject_info.get("1", {}).get("name", "Teacher 1")
    t2_name = subject_info.get("2", {}).get("name", "Teacher 2")

    # If both groups share the same teacher, skip the selection step
    if t1_name.strip().lower() == t2_name.strip().lower():
        context.user_data["cp_teacher_key"] = "1"
        return await _transition_to_experiment_step(query, context, subject)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t1_name, callback_data="coverpage:teacher:1")],
        [InlineKeyboardButton(t2_name, callback_data="coverpage:teacher:2")],
        [
            InlineKeyboardButton("Official", url=OFFICIAL_URL),
            InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
        ]
    ])
    await query.edit_message_text(
        f"🧑‍🏫 *Select Teacher for {subject}*\n\nPlease choose your course teacher:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return SELECT_TEACHER


async def cp_teacher_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    teacher_key = query.data.removeprefix("coverpage:teacher:")
    subject = context.user_data.get("cp_subject", "")

    roll, student = _get_student_by_user_id(query.from_user.id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /start.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["cp_teacher_key"] = teacher_key

    # Proceed to experiment selection/entry
    return await _transition_to_experiment_step(query, context, subject)


# ─── Step 2a : Experiment button clicked ──────────────────────────────────────

async def cp_experiment_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    exp_no = query.data.removeprefix("coverpage:exp:")
    experiments: dict = context.user_data.get("cp_experiments", {})
    detail = experiments.get(exp_no, {})

    context.user_data["cp_exp_no"]    = exp_no
    context.user_data["cp_exp_title"] = detail.get("title", "")
    context.user_data["cp_exp_type"]  = detail.get("type", "Lab Report")

    return await _ask_for_dates(query, context, edit=True)


# ─── Step 2b : Manual experiment button / prompt ─────────────────────────────

async def cp_experiment_manual_prompt(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✏️ *Manual Entry*\n\n"
        "Type the experiment details:\n\n"
        "`exp_no : Experiment Title`\n\n"
        "_Example:_ `3 : Kirchhoff's Laws`",
        parse_mode="Markdown",
        reply_markup=_footer_keyboard(),
    )
    return MANUAL_EXP_INPUT


async def cp_receive_manual_exp(update: Update, context: ContextTypes) -> str:
    text = update.message.text.strip()

    # Accept "exp_no : title" — colon is required
    parts = re.split(r"\s*:\s*", text, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        await update.message.reply_text(
            "⚠️ Invalid format. Please use:\n`exp_no : Experiment Title`\n\n"
            "_Example:_ `3 : Kirchhoff's Laws`",
            parse_mode="Markdown",
            reply_markup=_footer_keyboard(),
        )
        return MANUAL_EXP_INPUT

    exp_no    = parts[0].strip()
    exp_title = parts[1].strip()

    subject      = context.user_data["cp_subject"]
    subject_type = context.user_data.get("cp_subject_type", "sessional")

    # If theory, generated cover is Assignment. If sessional, Lab Report
    exp_type = "Assignment" if subject_type == "theory" else "Lab Report"

    context.user_data["cp_exp_no"]    = exp_no
    context.user_data["cp_exp_title"] = exp_title
    context.user_data["cp_exp_type"]  = exp_type

    # Save to MongoDB cache (updates/upserts sessional list)
    add_experiment_to_subject(subject, exp_no, exp_title, exp_type)

    return await _ask_for_dates_message(update, context)


# ─── Date asking helpers ───────────────────────────────────────────────────────

async def _build_date_ui(context: ContextTypes, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build the date prompt text + keyboard.
    Previously-used date pairs are rendered as quick-select buttons so the
    user can tap instead of typing.
    Returns (prompt_text, keyboard).
    """
    subject = context.user_data.get("cp_subject", "")
    exp_no  = context.user_data.get("cp_exp_no", "")

    rows = []
    if subject and exp_no:
        from bot.services.database import get_coverpage_dates_by_group
        records = get_coverpage_dates_by_group(subject, exp_no)
        for group_key, label in (("1", "1st 30"), ("2", "2nd 30")):
            rec = records.get(group_key)
            if rec:
                exp_d = _display_date(rec["date_of_experiment"])
                sub_d = _display_date(rec["date_of_submission"])
                # Store ISO dates in callback_data so handler can parse them
                cb = f"coverpage:dates:{rec['date_of_experiment']},{rec['date_of_submission']}"
                rows.append([
                    InlineKeyboardButton(
                        f"{label}: {exp_d}, {sub_d}",
                        callback_data=cb,
                    )
                ])

    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel",   callback_data="coverpage:cancel"),
    ])

    hint_text = "\n\n_Tap a date button above to use it, or type new dates below._" if rows[:-1] else ""
    prompt = (
        f"📅 *Enter Dates*{hint_text}\n\n"
        "Send both dates in this format:\n"
        "`dd-mm-yyyy, dd-mm-yyyy`\n\n"
        "_First date = Experimentation date_\n"
        "_Second date = Submission date_"
    )
    return prompt, InlineKeyboardMarkup(rows)


async def _ask_for_dates(query, context: ContextTypes, *, edit: bool) -> str:
    """Used when coming from a callback query (edit the existing message)."""
    prompt, keyboard = await _build_date_ui(context, query.from_user.id)
    if edit:
        await query.edit_message_text(prompt, parse_mode="Markdown", reply_markup=keyboard)
    return ENTER_DATES


async def _ask_for_dates_message(update: Update, context: ContextTypes) -> str:
    """Used when coming from a text message (send new message)."""
    prompt, keyboard = await _build_date_ui(context, update.effective_user.id)
    await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=keyboard)
    return ENTER_DATES


# ─── Quick-select date button handler ─────────────────────────────────────────

async def cp_dates_quick_select(update: Update, context: ContextTypes) -> int:
    """
    Called when the user taps one of the previously-used date buttons.
    Extracts ISO dates from callback_data and delegates to the shared
    date-processing logic (same as cp_receive_dates but without a text message).
    """
    query = update.callback_query
    await query.answer()

    # callback_data format: "coverpage:dates:YYYY-MM-DD,YYYY-MM-DD"
    payload = query.data.removeprefix("coverpage:dates:")
    parts   = payload.split(",", 1)
    if len(parts) != 2:
        await query.answer("⚠️ Bad date data, please type manually.", show_alert=True)
        return ENTER_DATES

    exp_date_iso, sub_date_iso = parts[0].strip(), parts[1].strip()

    # ── reuse the full generation pipeline ────────────────────────────────────
    user_id = query.from_user.id
    roll, student = _get_student_by_user_id(user_id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /start.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    subject   = context.user_data["cp_subject"]
    exp_no    = context.user_data["cp_exp_no"]
    exp_title = context.user_data["cp_exp_title"]
    exp_type  = context.user_data.get("cp_exp_type", "Lab Report")
    section   = student.get("section", "")
    name      = student.get("name", "")
    group     = _get_student_group(roll)

    teacher_key = context.user_data.get("cp_teacher_key")
    teacher     = _get_teacher(subject, roll, teacher_key)

    parts_sub = subject.split()
    dept_short = parts_sub[0] if parts_sub else "CSE"
    course_no  = f"{parts_sub[0]} - {parts_sub[1]}" if len(parts_sub) > 1 else subject

    subject_teachers = _load_json(TEACHER_SUBJECT_PATH)
    subject_info     = subject_teachers.get(subject, {})
    course_title     = subject_info.get("title", subject)

    dept_map = {
        "CSE":  "Computer Science & Engineering",
        "EEE":  "Electrical & Electronic Engineering",
        "MATH": "Mathematics",
        "HUM":  "Humanities",
    }
    department = teacher.get("department") or dept_map.get(dept_short, "Computer Science & Engineering")

    config = {
        "department":         department,
        "type":               exp_type,
        "courseNo":           course_no,
        "courseTitle":        course_title,
        "coverNo":            exp_no,
        "coverTitle":         exp_title,
        "teacherName":        teacher.get("name", ""),
        "teacherDesignation": teacher.get("designation", ""),
        "teacherDepartment":  teacher.get("department", ""),
        "dateOfExperiment":   exp_date_iso,
        "dateOfSubmission":   sub_date_iso,
        "watermark":          False,
        "courseCode":         False,
        "studentSeries":      False,
        "studentSession":     True,
        "assessmentTable":    False,
        "students": [
            {
                "id":      roll,
                "name":    name,
                "section": section,
            }
        ],
    }

    await query.edit_message_text("⏳ Generating your cover page...")

    try:
        from coverpage.generate import generate_from_dict

        COVERPAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = name.replace(" ", "_")
        fname    = f"{roll}_{safe_name}_Exp{exp_no}_{subject.replace(' ', '_')}.pdf"
        out_path = str(COVERPAGE_OUTPUT_DIR / fname)

        import asyncio as _asyncio
        loop = _asyncio.get_running_loop()
        await loop.run_in_executor(None, generate_from_dict, config, out_path)

        await query.delete_message()

        with open(out_path, "rb") as doc_file:
            await query.message.reply_document(
                document=doc_file,
                filename=fname,
                caption=(
                    f"✅ *Cover Page Ready!*\n\n"
                    f"*Subject:* {subject}\n"
                    f"*Exp {exp_no}:* {exp_title}\n"
                    f"*Experiment:* {_display_date(exp_date_iso)}\n"
                    f"*Submission:* {_display_date(sub_date_iso)}"
                ),
                parse_mode="Markdown",
            )

        try:
            os.remove(out_path)
        except Exception as e:
            print(f"[coverpage] Clean-up error: {e}")

        save_coverpage_record(
            user_id=user_id,
            roll=roll,
            subject=subject,
            exp_no=exp_no,
            group=group,
            date_of_experiment=exp_date_iso,
            date_of_submission=sub_date_iso,
        )

    except Exception as e:
        print(f"[coverpage] Quick-select generation error: {e}")
        await query.message.reply_text(f"❌ Failed to generate cover page.\nError: {e}")

    return ConversationHandler.END


# ─── Step 3 : Receive dates & generate PDF ───────────────────────────────────

async def cp_receive_dates(update: Update, context: ContextTypes) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id

    exp_date_iso, sub_date_iso = _parse_dates_input(text)
    if not exp_date_iso or not sub_date_iso:
        await update.message.reply_text(
            "⚠️ Invalid date format. Please use:\n"
            "`dd-mm-yyyy, dd-mm-yyyy`\n\n"
            "_Example:_ `19-07-2026, 26-07-2026`",
            parse_mode="Markdown",
            reply_markup=_footer_keyboard(),
        )
        return ENTER_DATES

    # Load student info
    roll, student = _get_student_by_user_id(user_id)
    if not roll:
        await update.message.reply_text(
            "❌ Could not find your student data. Please register first with /start.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    subject    = context.user_data["cp_subject"]
    exp_no     = context.user_data["cp_exp_no"]
    exp_title  = context.user_data["cp_exp_title"]
    exp_type   = context.user_data.get("cp_exp_type", "Lab Report")
    section    = student.get("section", "")
    name       = student.get("name", "")
    group      = _get_student_group(roll)

    teacher_key = context.user_data.get("cp_teacher_key")
    teacher = _get_teacher(subject, roll, teacher_key)

    # Derive course details from subject key (e.g. "EEE 2152" → "EEE - 2152")
    parts = subject.split()
    dept_short = parts[0] if parts else "CSE"
    if len(parts) > 1:
        course_no = f"{parts[0]} - {parts[1]}"
    else:
        course_no = subject

    subject_teachers = _load_json(TEACHER_SUBJECT_PATH)
    subject_info = subject_teachers.get(subject, {})
    course_title = subject_info.get("title", subject)

    dept_map = {
        "CSE":  "Computer Science & Engineering",
        "EEE":  "Electrical & Electronic Engineering",
        "MATH": "Mathematics",
        "HUM":  "Humanities",
    }
    department = teacher.get("department") or dept_map.get(dept_short, "Computer Science & Engineering")

    config = {
        "department":         department,
        "type":               exp_type,
        "courseNo":           course_no,
        "courseTitle":        course_title,
        "coverNo":            exp_no,
        "coverTitle":         exp_title,
        "teacherName":        teacher.get("name", ""),
        "teacherDesignation": teacher.get("designation", ""),
        "teacherDepartment":  teacher.get("department", ""),
        "dateOfExperiment":   exp_date_iso,
        "dateOfSubmission":   sub_date_iso,
        "watermark":          False,
        "courseCode":         False,
        "studentSeries":      False,
        "studentSession":     True,
        "assessmentTable":    False,
        "students": [
            {
                "id":      roll,
                "name":    name,
                "section": section,
            }
        ],
    }

    processing_msg = await update.message.reply_text("⏳ Generating your cover page...")

    try:
        # Import generate function (lazy to avoid import-time side-effects)
        from coverpage.generate import generate_from_dict

        COVERPAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = name.replace(" ", "_")
        fname = f"{roll}_{safe_name}_Exp{exp_no}_{subject.replace(' ', '_')}.pdf"
        out_path = str(COVERPAGE_OUTPUT_DIR / fname)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, generate_from_dict, config, out_path)

        await processing_msg.delete()

        with open(out_path, "rb") as doc_file:
            await update.message.reply_document(
                document=doc_file,
                filename=fname,
                caption=(
                    f"✅ *Cover Page Ready!*\n\n"
                    f"*Subject:* {subject}\n"
                    f"*Exp {exp_no}:* {exp_title}\n"
                    f"*Experiment:* {_display_date(exp_date_iso)}\n"
                    f"*Submission:* {_display_date(sub_date_iso)}"
                ),
                parse_mode="Markdown",
            )

        try:
            os.remove(out_path)
        except Exception as e:
            print(f"[coverpage] Clean-up error: {e}")

        # Persist to MongoDB
        save_coverpage_record(
            user_id=user_id,
            roll=roll,
            subject=subject,
            exp_no=exp_no,
            group=group,
            date_of_experiment=exp_date_iso,
            date_of_submission=sub_date_iso,
        )

    except Exception as e:
        print(f"[coverpage] Generation error: {e}")
        await processing_msg.edit_text(f"Failed to generate cover page.\nError: {e}")

    return ConversationHandler.END


# ─── Cancel ───────────────────────────────────────────────────────────────────

async def cp_cancel(update: Update, context: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Cover page generation cancelled.")
    return ConversationHandler.END