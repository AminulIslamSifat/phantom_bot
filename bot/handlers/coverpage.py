"""
Cover Page Conversation Handler
================================
Flow:
  "Cover Page" message
    → SELECT_SUBJECT   : show subject buttons
    → SELECT_EXPERIMENT: show experiment buttons or ask manual input
    → MANUAL_EXP_INPUT : receive typed "exp_no : exp_title"
    → ENTER_DATES      : ask for "dd-mm-yyyy, dd-mm-yyyy"

Every step shows [🌐 Official] [❌ Cancel] side by side at the bottom.
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
from bot.services.database import save_coverpage_record, get_subject_detail, add_experiment_to_subject

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent.parent  # project root
TEACHER_SUBJECT_PATH = _BASE / ".data" / "teacher_subject.json"
COVERPAGE_OUTPUT_DIR = _BASE / "coverpage" / "generated_covers"
OFFICIAL_URL = "https://ruet-cover-page.github.io/"

# ─── Conversation states ───────────────────────────────────────────────────────
SELECT_SUBJECT    = "cp_select_subject"
SELECT_EXPERIMENT = "cp_select_experiment"
MANUAL_EXP_INPUT  = "cp_manual_exp_input"
ENTER_DATES       = "cp_enter_dates"

# ─── Persistent footer keyboard ───────────────────────────────────────────────
def _footer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 Official", url=OFFICIAL_URL),
            InlineKeyboardButton("❌ Cancel",   callback_data="coverpage:cancel"),
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


def _get_teacher(subject: str, roll: str) -> dict:
    """
    Return teacher dict for a subject based on student's roll group.
    Group '1' (1st 30 of every 60) → teacher '1'
    Group '2' (2nd 30 of every 60) → teacher '2'
    """
    teacher_data = _load_json(TEACHER_SUBJECT_PATH)
    teachers_for_subject = teacher_data.get(subject, {})
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
        InlineKeyboardButton("🌐 Official", url=OFFICIAL_URL),
        InlineKeyboardButton("❌ Cancel",   callback_data="coverpage:cancel"),
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
        InlineKeyboardButton("🌐 Official", url=OFFICIAL_URL),
        InlineKeyboardButton("❌ Cancel",   callback_data="coverpage:cancel"),
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

async def cp_subject_selected(update: Update, context: ContextTypes) -> str:
    query = update.callback_query
    await query.answer()

    subject = query.data.removeprefix("coverpage:subject:")
    context.user_data["cp_subject"] = subject

    # Load experiment data from MongoDB
    subject_doc = get_subject_detail(subject)
    experiments = {}
    subject_type = "sessional"
    if subject_doc:
        experiments = subject_doc.get("experiments", {})
        subject_type = subject_doc.get("type", "sessional")

    context.user_data["cp_subject_type"] = subject_type

    if experiments:
        context.user_data["cp_experiments"] = experiments  # cache for later lookup
        await query.edit_message_text(
            f"📘 *{subject}*\n\nSelect an experiment or enter manually:",
            parse_mode="Markdown",
            reply_markup=_build_experiment_keyboard(experiments),
        )
        return SELECT_EXPERIMENT
    else:
        # No experiment data — skip straight to manual input
        await query.edit_message_text(
            f"📘 *{subject}*\n\n"
            "No experiment list found for this subject.\n"
            "Please type the experiment details in this format:\n\n"
            "`exp_no : Experiment Title`",
            parse_mode="Markdown",
            reply_markup=_footer_keyboard(),
        )
        return MANUAL_EXP_INPUT


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

async def _build_date_prompt(context: ContextTypes, user_id: int) -> str:
    """Build the date prompt, injecting per-group history hints if available."""
    roll, _student = _get_student_by_user_id(user_id)
    subject = context.user_data.get("cp_subject", "")
    exp_no  = context.user_data.get("cp_exp_no", "")

    hint_text = ""
    if subject and exp_no:
        from bot.services.database import get_coverpage_dates_by_group
        records = get_coverpage_dates_by_group(subject, exp_no)
        lines = []
        for group_key, label in (("1", "1st 30"), ("2", "2nd 30")):
            rec = records.get(group_key)
            if rec:
                exp_d = _display_date(rec["date_of_experiment"])
                sub_d = _display_date(rec["date_of_submission"])
                lines.append(f"`{label}: {exp_d}, {sub_d}`")
        if lines:
            hint_text = "\n\n📌 *Previously used dates:*\n" + "\n".join(lines)

    return (
        f"📅 *Enter Dates*{hint_text}\n\n"
        "Send both dates in this format:\n"
        "`dd-mm-yyyy, dd-mm-yyyy`\n\n"
        "_First date = Experimentation date_\n"
        "_Second date = Submission date_"
    )


async def _ask_for_dates(query, context: ContextTypes, *, edit: bool) -> str:
    """Used when coming from a callback query (edit the existing message)."""
    user_id = query.from_user.id
    prompt  = await _build_date_prompt(context, user_id)
    if edit:
        await query.edit_message_text(prompt, parse_mode="Markdown", reply_markup=_footer_keyboard())
    return ENTER_DATES


async def _ask_for_dates_message(update: Update, context: ContextTypes) -> str:
    """Used when coming from a text message (send new message)."""
    user_id = update.effective_user.id
    prompt  = await _build_date_prompt(context, user_id)
    await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=_footer_keyboard())
    return ENTER_DATES


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

    teacher = _get_teacher(subject, roll)

    # Derive course details from subject key (e.g. "EEE 2152" → dept EEE, no "2152")
    parts = subject.split()
    dept_short = parts[0] if parts else "CSE"
    course_no  = parts[-1] if len(parts) > 1 else subject

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
        "courseTitle":        subject,
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

        await update.message.reply_document(
            document=open(out_path, "rb"),
            filename=fname,
            caption=(
                f"✅ *Cover Page Ready!*\n\n"
                f"📘 *Subject:* {subject}\n"
                f"🔬 *Exp {exp_no}:* {exp_title}\n"
                f"📅 *Experiment:* {_display_date(exp_date_iso)}\n"
                f"📬 *Submission:* {_display_date(sub_date_iso)}"
            ),
            parse_mode="Markdown",
        )

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
        await processing_msg.edit_text(f"❌ Failed to generate cover page.\nError: {e}")

    return ConversationHandler.END


# ─── Cancel ───────────────────────────────────────────────────────────────────

async def cp_cancel(update: Update, context: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Cover page generation cancelled.")
    return ConversationHandler.END
