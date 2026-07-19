#!/usr/bin/env python3
"""
RUET Cover Page Bulk Generator
Requirements: fpdf2, pillow
Install:  uv pip install fpdf2 pillow
Run:      uv run python generate.py
"""

import json
import math
import sys
from datetime import datetime, date
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2 not installed. Run: uv pip install fpdf2 pillow")
    sys.exit(1)

SCRIPT_DIR   = Path(__file__).parent
ASSETS_DIR   = SCRIPT_DIR / "assets"
FONTS_DIR    = ASSETS_DIR / "fonts"
LOGO_PATH    = ASSETS_DIR / "RUET-Logo.png"
MOTTO_PATH   = ASSETS_DIR / "motto.png"
FONT_REGULAR = FONTS_DIR  / "TeXGyreTermes-Regular.ttf"
FONT_BOLD    = FONTS_DIR  / "TeXGyreTermes-Bold.ttf"
CONFIG_PATH  = SCRIPT_DIR / "bulk-config.json"
OUTPUT_DIR   = SCRIPT_DIR / "generated_covers"

PAGE_W, PAGE_H = 210, 297   # A4 mm
MARGIN_TOP     = 25.4        # 2.54cm
MARGIN_LEFT    = 30.0        # 3cm
MARGIN_RIGHT   = 25.4
MARGIN_BOTTOM  = 25.4
CONTENT_W      = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT   # ~154.6mm


def format_date(date_str):
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%-d %B %Y")
    except ValueError:
        return date_str


def get_section_from_id(student_id):
    if len(student_id) >= 7:
        try:
            roll = int(student_id[4:7])
            if roll < 60:    return "A"
            elif roll <= 120: return "B"
            elif roll <= 180: return "C"
        except ValueError:
            pass
    return ""


class CoverPage(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(False)
        self.set_margins(MARGIN_LEFT, MARGIN_TOP, MARGIN_RIGHT)
        # TeXGyreTermes — a high-quality Times New Roman clone
        self.add_font("Termes",  style="",   fname=str(FONT_REGULAR))
        self.add_font("Termes",  style="B",  fname=str(FONT_BOLD))
        self.add_font("Termes",  style="I",  fname=str(FONT_REGULAR))   # italic ≈ regular
        self.add_font("Termes",  style="BI", fname=str(FONT_BOLD))

    # ─── helpers ──────────────────────────────────────────────────────────────

    def centre_line(self, text, size, style="", line_h=None):
        self.set_font("Termes", style, size)
        lh = line_h or (size * 0.4 + 1.5)
        self.cell(CONTENT_W, lh, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def kv_aligned(self, key, value, key_col_w, size=16, gap_after=1):
        lh = size * 0.38 + 1
        self.set_font("Termes", "B", size)
        self.cell(key_col_w, lh, key)            # bold key
        self.cell(6,  lh, ":", align="C")        # colon
        self.set_font("Termes", "", size)
        self.cell(CONTENT_W - key_col_w - 6, lh, value, new_x="LMARGIN", new_y="NEXT")
        if gap_after:
            self.set_y(self.get_y() + gap_after)

    # ─── main generator ────────────────────────────────────────────────────────

    def generate(self, data):
        self.add_page()

        is_thesis  = data.get("type") == "Thesis"
        is_lab     = data.get("type") == "Lab Report"
        use_code   = data.get("courseCode", False)
        show_sess  = data.get("studentSession", True)
        show_ser   = data.get("studentSeries", False)
        watermark  = data.get("watermark", False)
        ass_table  = data.get("assessmentTable", False)

        student_id    = data.get("studentID", "")
        student_name  = data.get("studentName", "")
        student_sec   = data.get("studentSection", "")
        student_grp   = data.get("studentGroup", "")
        department    = data.get("department", "Computer Science & Engineering")
        course_no     = data.get("courseNo", "")
        course_title  = data.get("courseTitle", "")
        cover_no      = data.get("coverNo", "")
        cover_title   = data.get("coverTitle", "")
        teacher_name  = data.get("teacherName", "")
        teacher_desig = data.get("teacherDesignation", "")
        teacher_dept  = data.get("teacherDepartment", "")
        teacher2      = data.get("secondTeacherName", "")
        teacher2_des  = data.get("secondTeacherDesignation", "")
        date_sub  = format_date(data.get("dateOfSubmission"))
        date_exp  = format_date(data.get("dateOfExperiment"))

        # Watermark
        if watermark and LOGO_PATH.exists():
            self.image(str(LOGO_PATH), x=PAGE_W/2 - 40, y=PAGE_H/2 - 46, w=80, h=92)

        # 1. Motto at the very top — use the calligraphic motto.png if available
        if MOTTO_PATH.exists():
            # Centre the motto image; keep it small and inline with the top margin
            mw = 52
            self.image(str(MOTTO_PATH), x=MARGIN_LEFT + (CONTENT_W - mw) / 2,
                       y=MARGIN_TOP - 2, w=mw)
        else:
            self.set_xy(MARGIN_LEFT, MARGIN_TOP)
            self.set_font("Termes", "I", 12)
            self.cell(CONTENT_W, 5, "Heaven's Light is Our Guide",
                      align="C", new_x="LMARGIN", new_y="NEXT")

        # 2. Institution Name
        self.set_xy(MARGIN_LEFT, 36)
        self.centre_line("Rajshahi University of Engineering & Technology", 19, line_h=9)

        # 3. RUET Logo
        if LOGO_PATH.exists():
            lw, lh = 26, 30
            self.image(str(LOGO_PATH), x=MARGIN_LEFT + (CONTENT_W - lw) / 2, y=49, w=lw, h=lh)

        # 4. Department name
        self.set_xy(MARGIN_LEFT, 86)
        self.centre_line(f"Department of {department}", 16, line_h=7)
        if show_ser and len(student_id) >= 2:
            self.centre_line(f"{student_id[:2]} Series", 15, line_h=6)

        # 5. Course Info (Course No. & Title)
        self.set_xy(MARGIN_LEFT, 105)
        label = "Course Code" if use_code else "Course No."
        self.centre_line(f"{label}: {course_no}", 16, line_h=7)
        self.centre_line(f"Course Title: {course_title}", 16, line_h=7)

        # 6. Experiment Info
        self.set_xy(MARGIN_LEFT, 130)
        if is_thesis:
            self.centre_line("A project & thesis report on", 16, line_h=7)
            self.centre_line(cover_title, 16, line_h=7)
        else:
            item = "Experiment" if is_lab else data.get("type", "")
            KEY_W = 43
            if cover_no and cover_no != "0":
                self.kv_aligned(f"{item} No.", cover_no.zfill(2), key_col_w=KEY_W, gap_after=1.5)
            if cover_title:
                self.kv_aligned(f"{item} Title", cover_title, key_col_w=KEY_W, gap_after=0)

        # 7. Submitted by / Submitted to Box
        box_y  = 158 if ass_table else 168
        col_w  = CONTENT_W / 2
        avail_w = col_w - 6
        row_h  = 6.5
        head_h = 8

        # Build column items BEFORE drawing the box so we can measure heights.
        col_items = []
        if student_name: col_items.append(student_name)
        if student_grp:  col_items.append(f"Group: {student_grp}")
        col_items.append(f"Roll: {student_id}")
        if student_sec:  col_items.append(f"Section: {student_sec}")
        if show_sess and len(student_id) >= 2:
            try:
                yr = int(student_id[:2])
                col_items.append(f"Session: 20{yr:02d}-{yr+1:02d}")
            except ValueError:
                pass

        to_items = []
        if teacher_name:  to_items.append(teacher_name)
        if teacher_desig: to_items.append(teacher_desig)
        if teacher_dept:  to_items.append(f"Dept. of {teacher_dept}")
        if teacher_dept:  to_items.append("& Engineering, RUET")
        if teacher2:
            to_items.append("")
            to_items.append(teacher2)
            if teacher2_des: to_items.append(teacher2_des)

        def _rows(text: str) -> int:
            """Physical rows a string occupies at size-15 Termes in avail_w mm."""
            if not text:
                return 1
            self.set_font("Termes", "", 15)
            return max(1, math.ceil(self.get_string_width(text) / avail_w))

        by_rows = sum(_rows(t) for t in col_items)
        to_rows = sum(_rows(t) for t in to_items)
        box_h   = head_h + max(by_rows, to_rows) * row_h + 4

        # Draw box outline and centre divider
        self.rect(MARGIN_LEFT, box_y, CONTENT_W, box_h)
        self.line(MARGIN_LEFT + col_w, box_y, MARGIN_LEFT + col_w, box_y + box_h)

        left_x  = MARGIN_LEFT + 3
        right_x = MARGIN_LEFT + col_w + 3

        def _render_items(items: list[str], start_x: float, start_y: float) -> None:
            """Render a list of strings from (start_x, start_y), wrapping long lines."""
            y = start_y
            for txt in items:
                self.set_font("Termes", "", 15)
                self.set_xy(start_x, y)
                sw = self.get_string_width(txt)
                if sw <= avail_w:
                    self.cell(avail_w, row_h, txt, new_x="LEFT", new_y="NEXT")
                    y += row_h
                else:
                    self.multi_cell(avail_w, row_h, txt, new_x="LEFT", new_y="NEXT")
                    y = self.get_y()

        # Submitted by column
        self.set_xy(left_x, box_y + 2)
        self.set_font("Termes", "B", 15)
        self.cell(avail_w, head_h - 2, "Submitted by:", new_x="LMARGIN", new_y="NEXT")
        self.line(left_x, box_y + head_h - 1,
                  left_x + self.get_string_width("Submitted by:"), box_y + head_h - 1)
        _render_items(col_items, left_x, box_y + head_h)

        # Submitted to column
        to_label = "Supervised by:" if is_thesis else "Submitted to:"
        self.set_xy(right_x, box_y + 2)
        self.set_font("Termes", "B", 15)
        self.cell(avail_w, head_h - 2, to_label, new_x="LMARGIN", new_y="NEXT")
        self.line(right_x, box_y + head_h - 1,
                  right_x + self.get_string_width(to_label), box_y + head_h - 1)
        _render_items(to_items, right_x, box_y + head_h)

        # 8. Assessment Table
        if ass_table:
            table_y = box_y + box_h + 5
            self.set_xy(MARGIN_LEFT, table_y)
            self.set_font("Termes", "", 14)
            col = CONTENT_W / 3
            rh = 7
            self.cell(CONTENT_W, rh, "Assessment", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
            for lbl in ["CO", "PO", "Mark"]:
                self.cell(col, rh, lbl, border=1, align="C")
            self.ln()
            for val in [data.get("CO", ""), data.get("PO", ""), ""]:
                self.cell(col, rh, val, border=1, align="C")
            self.ln()

        # 9. Dates at the bottom
        dates_y = 245
        self.set_xy(MARGIN_LEFT, dates_y)
        DATE_KEY_W = 46
        if is_lab:
            self.kv_aligned("Date of Experiment", date_exp, key_col_w=DATE_KEY_W, size=15, gap_after=1.5)
            self.set_xy(MARGIN_LEFT, self.get_y())
        if not is_thesis:
            self.kv_aligned("Date of Submission", date_sub, key_col_w=DATE_KEY_W, size=15, gap_after=0)


def _build_student_data(config: dict, student: dict) -> dict:
    """Merge per-student overrides with the shared config into a single data dict."""
    sid  = student.get("id", "")
    name = student.get("name", "Unknown")
    sec  = student.get("section") or get_section_from_id(sid)
    return {
        "department":               student.get("department") or config.get("department", "Computer Science & Engineering"),
        "type":                     config.get("type", "Lab Report"),
        "courseNo":                 config.get("courseNo", ""),
        "courseTitle":              config.get("courseTitle", ""),
        "coverNo":                  config.get("coverNo", ""),
        "coverTitle":               config.get("coverTitle", ""),
        "teacherName":              student.get("teacherName") or config.get("teacherName", ""),
        "teacherDesignation":       student.get("teacherDesignation") or config.get("teacherDesignation", ""),
        "teacherDepartment":        student.get("teacherDepartment") or config.get("teacherDepartment", ""),
        "secondTeacherName":        config.get("secondTeacherName", ""),
        "secondTeacherDesignation": config.get("secondTeacherDesignation", ""),
        "dateOfSubmission":         config.get("dateOfSubmission", date.today().isoformat()),
        "dateOfExperiment":         config.get("dateOfExperiment"),
        "watermark":                config.get("watermark", False),
        "courseCode":               config.get("courseCode", False),
        "studentSeries":            config.get("studentSeries", False),
        "studentSession":           config.get("studentSession", True),
        "assessmentTable":          config.get("assessmentTable", False),
        "CO":                       config.get("CO", ""),
        "PO":                       config.get("PO", ""),
        "studentName":    name,
        "studentID":      sid,
        "studentSection": sec,
        "studentGroup":   student.get("group", ""),
    }


def generate_from_dict(config: dict, output_path: str) -> str:
    """
    Generate cover page PDF(s) from a config dict (same schema as bulk-config.json).
    Accepts a direct JSON dict instead of reading from disk.

    Args:
        config:      Config dict with student list and shared fields.
        output_path: Destination file path for the generated PDF.
                     If config has multiple students, files are written as
                     <output_path_stem>_<student_id>.pdf alongside the given path.

    Returns:
        The output_path of the first (or only) generated PDF.
    """
    students = config.get("students", [])
    if not students:
        raise ValueError("config must contain at least one student in 'students'")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    for asset in [LOGO_PATH, FONT_REGULAR, FONT_BOLD]:
        if not asset.exists():
            print(f"WARNING: Missing asset: {asset}")

    for i, student in enumerate(students):
        data = _build_student_data(config, student)

        if len(students) == 1:
            dest = out
        else:
            sid  = student.get("id", str(i))
            name = student.get("name", "student").replace(" ", "_")
            dest = out.parent / f"{sid}_{name}_Cover.pdf"

        pdf = CoverPage()
        pdf.generate(data)
        pdf.output(str(dest))

    return output_path


def main():
    if not CONFIG_PATH.exists():
        print(f"bulk-config.json not found at {CONFIG_PATH}")
        sys.exit(1)

    config   = json.loads(CONFIG_PATH.read_text())
    students = config.get("students", [])
    OUTPUT_DIR.mkdir(exist_ok=True)

    for asset in [LOGO_PATH, FONT_REGULAR, FONT_BOLD]:
        if not asset.exists():
            print(f"WARNING: Missing asset: {asset}")

    print(f"Generating covers for {len(students)} students...")

    for i, student in enumerate(students):
        sid  = student.get("id", "")
        name = student.get("name", "Unknown")

        data = _build_student_data(config, student)

        safe  = name.replace(" ", "_")
        fname = f"{sid}_{safe}_Cover.pdf"
        out   = OUTPUT_DIR / fname

        try:
            pdf = CoverPage()
            pdf.generate(data)
            pdf.output(str(out))
            print(f"  [{i+1}/{len(students)}] OK: {fname}")
        except Exception as e:
            print(f"  [{i+1}/{len(students)}] FAIL: {sid} ({name}): {e}")

    print(f"\nDone! PDFs in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
