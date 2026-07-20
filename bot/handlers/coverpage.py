"""
Cover Page Conversation Handler
================================
Flow:
  "Cover Page" message
    -> SELECT_SUBJECT   : show subject buttons (sessional always, theory only if it has experiments)
    -> SELECT_TEACHER   : show teacher buttons (skipped if both groups share a teacher)
    -> SELECT_EXPERIMENT: show experiment buttons or ask manual input
    -> MANUAL_EXP_INPUT : receive typed "exp_no : exp_title"
    -> ENTER_DATES      : ask for "dd-mm-yyyy, dd-mm-yyyy"

Every step shows [Official] [Cancel] side by side at the bottom.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    COVERPAGE_OUTPUT_DIR,
    OFFICIAL_URL,
    TEACHER_SUBJECT_PATH,
    user_data_path,
)
from bot.services.database import (
    add_experiment_to_subject,
    get_coverpage_dates_by_group,
    get_subject_experiments,
    save_coverpage_record,
)

# ─── Conversation states ───────────────────────────────────────────────────

SELECT_SUBJECT = "cp_select_subject"
SELECT_TEACHER = "cp_select_teacher"
SELECT_EXPERIMENT = "cp_select_experiment"
MANUAL_EXP_INPUT = "cp_manual_exp_input"
ENTER_DATES = "cp_enter_dates"

DEPARTMENT_MAP = {
    "CSE": "Computer Science & Engineering",
    "EEE": "Electrical & Electronic Engineering",
    "MATH": "Mathematics",
    "HUM": "Humanities",
}


# ─── JSON / data helpers ────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _subject_has_experiments(subject: str) -> bool:
    """True if MongoDB has a non-empty experiment list for this subject."""
    try:
        subject_doc = get_subject_experiments(subject)
    except Exception as e:
        print(f"[coverpage] get_subject_experiments error for '{subject}': {e}")
        return False

    if not subject_doc:
        return False
    return bool(subject_doc.get("experiments"))


def _get_student_by_user_id(user_id: int) -> tuple[str, dict] | tuple[None, None]:
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
    Teacher group from roll number, repeating every 60 students:
      001-030, 061-090, 121-150 -> '1'
      031-060, 091-120, 151-180 -> '2'
    """
    try:
        suffix = int(roll[-3:])
        pos = (suffix - 1) % 60
        return "1" if pos < 30 else "2"
    except (ValueError, IndexError):
        return "1"


def _get_teacher(subject: str, roll: str, teacher_key: str = None) -> dict:
    teacher_data = _load_json(TEACHER_SUBJECT_PATH)
    teachers_for_subject = teacher_data.get(subject, {})
    if not teacher_key:
        teacher_key = _get_student_group(roll)
    return teachers_for_subject.get(teacher_key) or teachers_for_subject.get("1", {})


def _course_details(subject: str) -> tuple[str, str, str]:
    """Returns (dept_short, course_no, course_title)."""
    parts = subject.split()
    dept_short = parts[0] if parts else "CSE"
    course_no = f"{parts[0]} - {parts[1]}" if len(parts) > 1 else subject

    subject_info = _load_json(TEACHER_SUBJECT_PATH).get(subject, {})
    course_title = subject_info.get("title", subject)
    return dept_short, course_no, course_title


# ─── Date helpers ───────────────────────────────────────────────────────────

def _parse_date(raw: str) -> str | None:
    """Accepts dd-mm-yyyy or dd/mm/yyyy, returns ISO yyyy-mm-dd or None."""
    raw = raw.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_dates_input(text: str) -> tuple[str | None, str | None]:
    """Parses 'dd-mm-yyyy, dd-mm-yyyy' -> (exp_date_iso, sub_date_iso)."""
    parts = re.split(r"\s*,\s*", text.strip())
    if len(parts) != 2:
        return None, None
    return _parse_date(parts[0]), _parse_date(parts[1])


def _display_date(iso: str) -> str:
    """'2026-07-19' -> '19-07-2026'"""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return iso


# ─── Keyboards ───────────────────────────────────────────────────────────────

def _footer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
    ]])


def _build_subject_keyboard(subjects: list[str]) -> InlineKeyboardMarkup:
    """One subject per row, then footer."""
    rows = [[InlineKeyboardButton(s, callback_data=f"coverpage:subject:{s}")] for s in subjects]
    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _build_teacher_keyboard(t1_name: str, t2_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t1_name, callback_data="coverpage:teacher:1")],
        [InlineKeyboardButton(t2_name, callback_data="coverpage:teacher:2")],
        [
            InlineKeyboardButton("Official", url=OFFICIAL_URL),
            InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
        ],
    ])


def _build_experiment_keyboard(experiments: dict) -> InlineKeyboardMarkup:
    """One experiment per row ('Exp N: Title'), plus manual entry, then footer."""
    rows = []
    for exp_no, detail in experiments.items():
        title = detail.get("title", "")
        label = f"Exp {exp_no}: {title[:40]}{'…' if len(title) > 40 else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"coverpage:exp:{exp_no}")])
    rows.append([InlineKeyboardButton("✏️ Enter Manually", callback_data="coverpage:exp:manual")])
    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


# ─── Entry point: subject selection ────────────────────────────────────────

def _available_subjects(teacher_data: dict) -> list[str]:
    """Sessional subjects are always available; theory subjects only if they have experiments listed."""
    subjects = []
    for subject, info in teacher_data.items():
        subject_type = info.get("type", "sessional")
        if subject_type == "sessional":
            subjects.append(subject)
        elif subject_type == "theory" and _subject_has_experiments(subject):
            subjects.append(subject)
    return subjects


async def cover_page_start(update: Update, context: ContextTypes) -> str:
    """Entry: triggered by the 'Cover Page' reply keyboard button."""
    context.user_data.clear()

    teacher_data = _load_json(TEACHER_SUBJECT_PATH)
    subjects = _available_subjects(teacher_data)

    if not subjects:
        await update.message.reply_text(
            "⚠️ No subjects are currently available for cover page generation.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📄 *Cover Page Generator*\n\nPlease Select your subject from below:",
        parse_mode="Markdown",
        reply_markup=_build_subject_keyboard(subjects),
    )
    return SELECT_SUBJECT


# ─── Step 1: subject -> teacher / experiment ───────────────────────────────

async def _transition_to_experiment_step(query, context: ContextTypes, subject: str) -> str:
    subject_doc = get_subject_experiments(subject)
    subject_info = _load_json(TEACHER_SUBJECT_PATH).get(subject, {})
    subject_type = subject_info.get("type", "sessional")

    experiments = {}
    if subject_doc:
        experiments = subject_doc.get("experiments", {})
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

    roll, student = _get_student_by_user_id(query.from_user.id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /register.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    subject_info = _load_json(TEACHER_SUBJECT_PATH).get(subject, {})
    context.user_data["cp_subject_type"] = subject_info.get("type", "sessional")

    t1_name = subject_info.get("1", {}).get("name", "Teacher 1")
    t2_name = subject_info.get("2", {}).get("name", "Teacher 2")

    if t1_name.strip().lower() == t2_name.strip().lower():
        context.user_data["cp_teacher_key"] = "1"
        return await _transition_to_experiment_step(query, context, subject)

    await query.edit_message_text(
        f"🧑‍🏫 *Select Teacher for {subject}*\n\nPlease choose your course teacher:",
        parse_mode="Markdown",
        reply_markup=_build_teacher_keyboard(t1_name, t2_name),
    )
    return SELECT_TEACHER


async def cp_teacher_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    teacher_key = query.data.removeprefix("coverpage:teacher:")
    subject = context.user_data.get("cp_subject", "")

    roll, _ = _get_student_by_user_id(query.from_user.id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /register.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["cp_teacher_key"] = teacher_key
    return await _transition_to_experiment_step(query, context, subject)


# ─── Step 2: experiment selection / manual entry ───────────────────────────

async def cp_experiment_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    exp_no = query.data.removeprefix("coverpage:exp:")
    experiments: dict = context.user_data.get("cp_experiments", {})
    detail = experiments.get(exp_no, {})

    context.user_data["cp_exp_no"] = exp_no
    context.user_data["cp_exp_title"] = detail.get("title", "")
    context.user_data["cp_exp_type"] = detail.get("type", "Lab Report")

    return await _ask_for_dates(query, context)


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

    parts = re.split(r"\s*:\s*", text, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        await update.message.reply_text(
            "⚠️ Invalid format. Please use:\n`exp_no : Experiment Title`\n\n"
            "_Example:_ `3 : Kirchhoff's Laws`",
            parse_mode="Markdown",
            reply_markup=_footer_keyboard(),
        )
        return MANUAL_EXP_INPUT

    exp_no, exp_title = parts[0].strip(), parts[1].strip()
    subject = context.user_data["cp_subject"]
    subject_type = context.user_data.get("cp_subject_type", "sessional")
    exp_type = "Assignment" if subject_type == "theory" else "Lab Report"

    context.user_data["cp_exp_no"] = exp_no
    context.user_data["cp_exp_title"] = exp_title
    context.user_data["cp_exp_type"] = exp_type

    add_experiment_to_subject(subject, exp_no, exp_title, exp_type)

    return await _ask_for_dates(update, context)


# ─── Date step ───────────────────────────────────────────────────────────────

async def _build_date_ui(context: ContextTypes) -> tuple[str, InlineKeyboardMarkup]:
    """Builds the date prompt text + keyboard, with quick-select buttons for previously-used dates."""
    subject = context.user_data.get("cp_subject", "")
    exp_no = context.user_data.get("cp_exp_no", "")

    rows = []
    if subject and exp_no:
        records = get_coverpage_dates_by_group(subject, exp_no)
        for group_key, label in (("1", "1st 30"), ("2", "2nd 30")):
            rec = records.get(group_key)
            if not rec:
                continue
            exp_d = _display_date(rec["date_of_experiment"])
            sub_d = _display_date(rec["date_of_submission"])
            cb = f"coverpage:dates:{rec['date_of_experiment']},{rec['date_of_submission']}"
            rows.append([InlineKeyboardButton(f"{label}: {exp_d}, {sub_d}", callback_data=cb)])

    has_quick_select = bool(rows)
    rows.append([
        InlineKeyboardButton("Official", url=OFFICIAL_URL),
        InlineKeyboardButton("Cancel", callback_data="coverpage:cancel"),
    ])

    hint = "\n\n_Tap a date button above to use it, or type new dates below._" if has_quick_select else ""
    prompt = (
        f"📅 *Enter Dates*{hint}\n\n"
        "Send both dates in this format:\n"
        "`dd-mm-yyyy, dd-mm-yyyy`\n\n"
        "_First date = Experimentation date_\n"
        "_Second date = Submission date_"
    )
    return prompt, InlineKeyboardMarkup(rows)


async def _ask_for_dates(source, context: ContextTypes) -> str:
    """Accepts either a CallbackQuery (edits message) or an Update (sends new message)."""
    prompt, keyboard = await _build_date_ui(context)
    if isinstance(source, Update):
        await source.message.reply_text(prompt, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await source.edit_message_text(prompt, parse_mode="Markdown", reply_markup=keyboard)
    return ENTER_DATES


def _build_cover_config(context: ContextTypes, roll: str, student: dict,
                         exp_date_iso: str, sub_date_iso: str) -> dict:
    subject = context.user_data["cp_subject"]
    exp_no = context.user_data["cp_exp_no"]
    exp_title = context.user_data["cp_exp_title"]
    exp_type = context.user_data.get("cp_exp_type", "Lab Report")

    teacher_key = context.user_data.get("cp_teacher_key")
    teacher = _get_teacher(subject, roll, teacher_key)
    dept_short, course_no, course_title = _course_details(subject)
    department = teacher.get("department") or DEPARTMENT_MAP.get(dept_short, "Computer Science & Engineering")

    return {
        "department": department,
        "type": exp_type,
        "courseNo": course_no,
        "courseTitle": course_title,
        "coverNo": exp_no,
        "coverTitle": exp_title,
        "teacherName": teacher.get("name", ""),
        "teacherDesignation": teacher.get("designation", ""),
        "teacherDepartment": teacher.get("department", ""),
        "dateOfExperiment": exp_date_iso,
        "dateOfSubmission": sub_date_iso,
        "watermark": False,
        "courseCode": False,
        "studentSeries": False,
        "studentSession": True,
        "assessmentTable": False,
        "students": [{
            "id": roll,
            "name": student.get("name", ""),
            "section": student.get("section", ""),
        }],
    }


async def _generate_and_send(context: ContextTypes, user_id: int, roll: str, student: dict,
                              exp_date_iso: str, sub_date_iso: str, send_document) -> None:
    """Runs the PDF generation pipeline and hands the file to `send_document(path, filename, caption)`."""
    subject = context.user_data["cp_subject"]
    exp_no = context.user_data["cp_exp_no"]
    exp_title = context.user_data["cp_exp_title"]
    group = _get_student_group(roll)

    config = _build_cover_config(context, roll, student, exp_date_iso, sub_date_iso)

    from coverpage.generate import generate_from_dict

    COVERPAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = student.get("name", "").replace(" ", "_")
    fname = f"{roll}_{safe_name}_Exp{exp_no}_{subject.replace(' ', '_')}.pdf"
    out_path = str(COVERPAGE_OUTPUT_DIR / fname)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, generate_from_dict, config, out_path)

    caption = (
        f"✅ *Cover Page Ready!*\n\n"
        f"*Subject:* {subject}\n"
        f"*Exp {exp_no}:* {exp_title}\n"
        f"*Experiment:* {_display_date(exp_date_iso)}\n"
        f"*Submission:* {_display_date(sub_date_iso)}"
    )

    with open(out_path, "rb") as doc_file:
        await send_document(doc_file, fname, caption)

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


async def cp_dates_quick_select(update: Update, context: ContextTypes) -> int:
    """Called when the user taps a previously-used date button."""
    query = update.callback_query
    await query.answer()

    payload = query.data.removeprefix("coverpage:dates:")
    parts = payload.split(",", 1)
    if len(parts) != 2:
        await query.answer("⚠️ Bad date data, please type manually.", show_alert=True)
        return ENTER_DATES

    exp_date_iso, sub_date_iso = parts[0].strip(), parts[1].strip()

    user_id = query.from_user.id
    roll, student = _get_student_by_user_id(user_id)
    if not roll:
        await query.edit_message_text(
            "❌ Could not find your student data. Please register first with /register.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    await query.edit_message_text("⏳ Generating your cover page...")

    async def send_document(doc_file, fname, caption):
        await query.delete_message()
        await query.message.reply_document(
            document=doc_file, filename=fname, caption=caption, parse_mode="Markdown",
        )

    try:
        await _generate_and_send(context, user_id, roll, student, exp_date_iso, sub_date_iso, send_document)
    except Exception as e:
        print(f"[coverpage] Quick-select generation error: {e}")
        await query.message.reply_text(f"❌ Failed to generate cover page.\nError: {e}")

    return ConversationHandler.END


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

    roll, student = _get_student_by_user_id(user_id)
    if not roll:
        await update.message.reply_text(
            "❌ Could not find your student data. Please register first with /register.",
            reply_markup=_footer_keyboard(),
        )
        return ConversationHandler.END

    processing_msg = await update.message.reply_text("⏳ Generating your cover page...")

    async def send_document(doc_file, fname, caption):
        await processing_msg.delete()
        await update.message.reply_document(
            document=doc_file, filename=fname, caption=caption, parse_mode="Markdown",
        )

    try:
        await _generate_and_send(context, user_id, roll, student, exp_date_iso, sub_date_iso, send_document)
    except Exception as e:
        print(f"[coverpage] Generation error: {e}")
        await processing_msg.edit_text(f"Failed to generate cover page.\nError: {e}")

    return ConversationHandler.END


# ─── Cancel ─────────────────────────────────────────────────────────────────

async def cp_cancel(update: Update, context: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Cover page generation cancelled.")
    return ConversationHandler.END