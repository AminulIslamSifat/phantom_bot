# 🧠 Developer Helper — Phantom Bot Internals

> A complete technical reference for every request type, the exact functions involved,  
> how data flows between files, and what each layer does.

---

## 📋 Table of Contents

- [Architecture Overview](#-architecture-overview)
- [Startup & Data Loading](#-startup--data-loading)
- [Handler Registration Map](#-handler-registration-map)
- [Request Flows](#-request-flows)
  - [/start — Registration Check](#start--registration-check)
  - [Registration Conversation](#registration-conversation)
  - [Routine Request](#routine-request)
  - [Schedule Request](#schedule-request)
  - [Resources → Drive](#resources--drive)
  - [Resources → Syllabus](#resources--syllabus)
  - [Resources → YouTube Downloader](#resources--youtube-downloader)
  - [Cover Page — Full 5-Step Flow](#cover-page--full-5-step-flow)
  - [Admin Panel](#admin-panel)
  - [Notice Broadcast Conversation](#notice-broadcast-conversation)
- [Data Storage Reference](#-data-storage-reference)
- [MongoDB Collections Reference](#-mongodb-collections-reference)
- [File Dependency Graph](#-file-dependency-graph)
- [Key Utility Functions](#-key-utility-functions)

---

## 🏗 Architecture Overview

```
bot/main.py  ←── Entry point
    │
    ├── load_data()               # Sync MongoDB → .data/ JSON caches
    ├── start_server()            # aiohttp health check on /
    └── app.run_polling()         # Start Telegram polling
            │
            └── bot/bot.py        # ApplicationBuilder + all handler registration
                    │
                    ├── CommandHandler (/start, /admin, /help)
                    ├── MessageHandler (reply keyboard routing)
                    ├── ConversationHandlers (YT, Registration, Notice, Cover Page)
                    └── CallbackQueryHandlers (admin:*, resources:*, syllabus:*, coverpage:*)
```

**Two parallel threads at runtime:**
- `asyncio` event loop handles all Telegram I/O
- `threading.Thread` is used only for the synchronous `update_routine()` call to avoid blocking

---

## 🚀 Startup & Data Loading

**File:** `bot/main.py`  
**Entry point:** `if __name__ == '__main__':`

```
main.py
  └── load_data()  ← bot/services/database.py
        ├── load_teacher_data()        # HTTP GET → TEACHER_API_URL → .data/teacher_data.json
        ├── load_users()               # MongoDB phantom_bot_db → .data/user_data.json
        ├── load_routine_odd_even_sequence()  # MongoDB → .data/routine_odd_even_week.json
        ├── load_subject_teachers()    # MongoDB → .data/subject_teachers.json
        └── load_subject_experiments() # MongoDB → .data/subject_experiments.json
```

**Why local caching?** MongoDB round-trips add latency for high-frequency reads. All user data, subject/teacher data, and routine state are cached locally and only updated on startup or on explicit admin actions.

---

## 🗺 Handler Registration Map

Defined in **`bot/bot.py`**:

| Trigger | Pattern / Filter | Handler Function | File |
|---|---|---|---|
| `/start` command | `CommandHandler` | `start()` | `handlers/command.py` |
| `/admin` command | `CommandHandler` | `admin()` | `handlers/command.py` |
| `/help` command | `CommandHandler` | `help()` | `handlers/command.py` |
| Text: `"Routine"` | `MessageHandler(Regex)` | `message_handler()` → `routine()` | `handlers/message.py` |
| Text: `"Schedule"` | `MessageHandler(Regex)` | `message_handler()` → `schedule()` | `handlers/message.py` |
| Text: `"Resources"` | `MessageHandler(Regex)` | `message_handler()` → `resources()` | `handlers/message.py` |
| Text: `"Cover Page"` | `MessageHandler(Regex)` | `cover_page_start()` | `handlers/coverpage.py` |
| Callback: `admin:*` | `CallbackQueryHandler` | `admin_button_handler()` | `handlers/inline_button.py` |
| Callback: `resources:*` | `CallbackQueryHandler` | `resources_button_handler()` | `handlers/inline_button.py` |
| Callback: `resources:syllabus:official:*` | `CallbackQueryHandler` | `syllabus_id_handler()` | `handlers/inline_button.py` |
| Callback: `resources:yt_downloader:download:*` | `CallbackQueryHandler` | `yt_download_file_id_handler()` | `handlers/inline_button.py` |
| Callback: `register` | ConversationHandler entry | `ask_for_roll()` | `handlers/conversation.py` |
| Callback: `resources:yt_downloader` | ConversationHandler entry | `start_yt_downloader()` | `handlers/conversation.py` |
| Callback: `admin:notice` | ConversationHandler entry | `ask_for_notice()` | `handlers/conversation.py` |

---

## 🔄 Request Flows

---

### `/start` — Registration Check

**Trigger:** User sends `/start`

```
User sends /start
    ↓
command.py :: start(update, context)
    ↓
Reads .data/user_data.json  (loaded from MongoDB at startup)
    ↓
Checks if update.effective_user.id is in any user's "user_id" field
    ├── NOT found → reply "Please register" + register_keyboard (InlineKeyboardMarkup)
    └── Found     → reply "Welcome Back" + main_keyboard (ReplyKeyboardMarkup from config.py)
```

**Data read:** `.data/user_data.json` (local cache, built from MongoDB `phantom_bot_db/<roll>` collections)

---

### Registration Conversation

**Trigger:** User taps the "Register" inline button (`callback_data="register"`)

**ConversationHandler states:** `recieve_roll`

```
Callback: "register"
    ↓
conversation.py :: ask_for_roll(update, context)
    → query.answer()
    → edit message: "Please Enter your roll number"
    → returns state "recieve_roll"
    ↓
User types roll number
    ↓
conversation.py :: recieve_roll(update, context)
    ↓
    Validates: int(text)  [must be numeric]
    ↓
    Reads .data/user_data.json
    Finds the matching roll entry
    Sets data[roll]["user_id"] = telegram_user_id
    Writes back to .data/user_data.json
    ↓
    MongoDB update:
        db[str(roll)].update_one(
            {"roll": str(roll)},
            {"$set": {"user_id": user_id}}
        )
    ↓
    reply "Registration Complete."
    → returns ConversationHandler.END
```

**Data written:**
- `.data/user_data.json` — sets user_id field for the roll
- `MongoDB phantom_bot_db/<roll>` — sets user_id field

---

### Routine Request

**Trigger:** User taps the "Routine" reply keyboard button

```
User taps "Routine"
    ↓
message.py :: message_handler(update, context)
    → predefined_commands["Routine"] = routine
    ↓
message.py :: routine(update, context)
    ↓
services/routine.py :: is_even_week()
    → storage.py :: get_routine_week()
        → reads .data/routine_odd_even_week.json → returns "odd" or "even"
    → Calculates day count from calibration date
    → Returns (is_even: bool, activation_date: str)
    ↓
Selects:
    routine_path_even_week = "resources/routine/routine_even_week.png"
    routine_path_odd_week  = "resources/routine/routine_odd_week.png"
    (from config.py)
    ↓
context.bot.send_photo(
    chat_id=user_id,
    photo=routine_path,         # local file path
    caption="applicable from {activation_date}",
    reply_markup=routine_keyboard   # [Live Routine] URL button
)
```

**Data read:** `.data/routine_odd_even_week.json`, local PNG file

---

### Schedule Request

**Trigger:** User taps the "Schedule" reply keyboard button

```
User taps "Schedule"
    ↓
message.py :: message_handler(update, context)
    → predefined_commands["Schedule"] = schedule
    ↓
message.py :: schedule(update, context)
    ↓
services/schedule.py :: get_schedule()
    ↓
    Connects to MongoDB "schedule" database
    Reads all documents from: ct, assignment, semester_final, backlog
    (+ any extra collections found dynamically)
    ↓
    For each document:
        Parses date string "YYYY-MM-DD"
        Calculates countdown: delta = parsed_date - today
        Labels: Today / Tomorrow / Xd left / Xd ago
    ↓
    Sorts all events chronologically
    ↓
    Builds formatted Markdown string with emojis
    Returns string
    ↓
update.message.reply_text(schedule_text, parse_mode="Markdown")
```

**Data read:** MongoDB `schedule` database (live query, not cached)

---

### Resources → Drive

**Trigger:** User taps "Resources" → then "Drive"

```
User taps "Resources"
    ↓
message.py :: resources(update, context)
    → reply with resources_keyboard (InlineKeyboardMarkup defined in message.py)
    ↓
User taps "Drive"
    ↓
inline_button.py :: resources_button_handler(update, context)
    → query.data == "resources:drive"
    → edit message with resources_drive_keyboard
        (built from config.available_drive dict at module load time)
    ↓
Each drive button has a URL, no further handler needed
```

**Data read:** `config.available_drive` dict (hardcoded in `config.py`)

---

### Resources → Syllabus

**Trigger:** User taps "Resources" → "Syllabus" → "Official"/"Unofficial" → specific subject

```
User taps "Syllabus"
    ↓
inline_button.py :: resources_button_handler()
    → query.data == "resources:syllabus"
    → edit with resources_syllabus_keyboard [Official / Unofficial]
    ↓
User taps "Official"
    ↓
inline_button.py :: resources_button_handler()
    → query.data == "resources:syllabus:official"
    → edit with resources_syllabus_official_keyboard
        (built from available_syllabus_official dict — scanned from resources/syllabus/official/ at startup)
    ↓
User taps a subject button (e.g. "CSE 2101")
    ↓
inline_button.py :: syllabus_id_handler(update, context)
    → pattern: "resources:syllabus:official:*"
    → extracts syllabus_key from callback_data
    → looks up path: available_syllabus_official[syllabus_key]
    → context.bot.send_document(chat_id, open(syllabus_path, "rb"))
```

**Data read:** Local PDF files in `resources/syllabus/official/` or `unofficial/`

---

### Resources → YouTube Downloader

**Trigger:** User taps "Resources" → "YT-downloader"

**ConversationHandler states:** `recieve_yt_link` (note the typo in the state name is intentional — matches bot.py)

```
User taps "YT-downloader"
    ↓
conversation.py :: start_yt_downloader(update, context)
    → query.answer()
    → edit message: "Enter the link of the video"
    → returns state "recieve_yt_link"
    ↓
User sends URL text
    ↓
conversation.py :: receieve_yt_link(update, context)
    ↓
    Validates: link.startswith("http")
    Stores: context.user_data["yt_link"] = link
    ↓
    asyncio executor (non-blocking):
        scripts/yt_downloader.py :: get_available_video_formats(link)
            → runs yt-dlp to list all formats
            → groups into quality tiers: 4K, 1440p, 1080p, 720p, 480p, 360p, Audio
            → returns dict {label: (format_id, human_size)}
    ↓
    Builds format keyboard:
        video: callback_data = "resources:yt_downloader:download:v|{tier}"
        audio: callback_data = "resources:yt_downloader:download:a"
    ↓
    edit message with formats keyboard
    → returns ConversationHandler.END   (conversation ends here, download is a separate handler)
    ↓
User taps a format button
    ↓
inline_button.py :: yt_download_file_id_handler(update, context)
    → pattern: "resources:yt_downloader:download:*"
    → Reads context.user_data["yt_link"]  (from previous conversation session)
    → Parses format: "v|1080p" → format_selector = "best[height<=1080]/..."
                     "a"      → format_selector = "bestaudio/best"
    → edit message: "Download Started..."
    ↓
    scripts/yt_downloader.py :: download_and_upload(bot, chat_id, link, format_selector)
        → yt-dlp downloads to .data/tmp/
        → tg_client (Telethon) uploads to PHANTOM_BOT_CHANNEL_ID
        → bot.forward_message() to user's chat_id
        → deletes tmp file
```

**Data flow:**
- `context.user_data["yt_link"]` bridges the two handlers (conversation → callback)
- Telethon `tg_client` (defined in `config.py`) handles the large file upload (bypasses 50 MB bot limit)

---

### Cover Page — Full 5-Step Flow

This is the most complex flow. The entire conversation is managed by `handlers/coverpage.py`.

**ConversationHandler states:**
- `cp_select_subject`
- `cp_select_teacher`
- `cp_select_experiment`
- `cp_manual_exp_input`
- `cp_enter_dates`

---

#### Step 1 — Entry: Cover Page button

```
User taps "Cover Page" (reply keyboard)
    ↓
coverpage.py :: cover_page_start(update, context)
    → context.user_data.clear()   # fresh session
    → reads .data/subject_teachers.json  (via _load_json())
    → extracts subject keys list
    → reply with _build_subject_keyboard(subjects)
        → 2 subjects per row + [🌐 Official][❌ Cancel] footer
    → returns SELECT_SUBJECT state
```

---

#### Step 2 — Subject Selected

```
User taps a subject button
    ↓
coverpage.py :: cp_subject_selected(update, context)
    → stores: context.user_data["cp_subject"] = subject
    ↓
    _get_student_by_user_id(query.from_user.id)
        → reads .data/user_data.json
        → finds roll whose user_id matches
        → returns (roll, student_dict)
    ↓
    reads .data/subject_teachers.json
    gets subject_info = teachers_data[subject]
    ↓
    checks: student["teacher_choices"].get(subject)
    ├── Already chosen → stores cp_teacher_key in user_data
    │                 → calls _transition_to_experiment_step()
    │                 → returns SELECT_EXPERIMENT or MANUAL_EXP_INPUT state
    │
    └── Not chosen    → shows teacher selection keyboard
                      → returns SELECT_TEACHER state
```

---

#### Step 3 — Teacher Selected (first time only)

```
User taps a teacher button ("coverpage:teacher:1" or "coverpage:teacher:2")
    ↓
coverpage.py :: cp_teacher_selected(update, context)
    → extracts teacher_key from callback_data
    → stores: context.user_data["cp_teacher_key"] = teacher_key
    ↓
    database.py :: save_user_teacher_choice(roll, subject, teacher_key)
        → MongoDB: db[roll].update_one({"$set": {"teacher_choices.{subject}": teacher_key}})
        → updates .data/user_data.json locally
    ↓
    calls _transition_to_experiment_step(query, context, subject)
```

**`_transition_to_experiment_step()` internal:**

```
_transition_to_experiment_step(query, context, subject)
    ↓
    database.py :: get_subject_experiments(subject)
        → normalizes subject name: re.sub(r"[\s\-]+", "", key).upper()
        → MongoDB query: db["subject_experiments"].find_one({"normalized": normalized})
        → returns full experiment document or None
    ↓
    If experiments dict is non-empty:
        edit message with _build_experiment_keyboard(experiments)
            → one button per experiment: "Exp N: Title"
            → [✏️ Enter Manually] button
            → [🌐 Official][❌ Cancel] footer
        returns SELECT_EXPERIMENT state
    ↓
    If no experiments:
        edit message: "No experiment list found, type manually"
        returns MANUAL_EXP_INPUT state
```

---

#### Step 4a — Experiment Button Clicked

```
User taps an experiment button ("coverpage:exp:{exp_no}")
    ↓
coverpage.py :: cp_experiment_selected(update, context)
    → extracts exp_no from callback_data
    → looks up: context.user_data["cp_experiments"][exp_no]
    → stores:
        context.user_data["cp_exp_no"]    = exp_no
        context.user_data["cp_exp_title"] = detail["title"]
        context.user_data["cp_exp_type"]  = detail["type"]
    ↓
    calls _ask_for_dates(query, context, edit=True)
    → returns ENTER_DATES state
```

#### Step 4b — Manual Experiment Input

```
User taps "✏️ Enter Manually"
    ↓
coverpage.py :: cp_experiment_manual_prompt(update, context)
    → edit message with format instructions
    → returns MANUAL_EXP_INPUT state
    ↓
User types: "3 : Kirchhoff's Laws"
    ↓
coverpage.py :: cp_receive_manual_exp(update, context)
    → re.split(r"\s*:\s*", text, maxsplit=1)
    → validates both parts non-empty
    → stores cp_exp_no, cp_exp_title, cp_exp_type in user_data
    ↓
    database.py :: add_experiment_to_subject(subject, exp_no, title, exp_type)
        → normalizes subject name
        → finds or creates document in db["subject_experiments"]
        → adds exp entry if not already there
    ↓
    calls _ask_for_dates_message(update, context)
    → returns ENTER_DATES state
```

---

#### Step 5 — Date Entry Phase

```
coverpage.py :: _build_date_ui(context, user_id)
    ↓
    database.py :: get_coverpage_dates_by_group(subject, exp_no)
        → for group in ("1", "2"):
            db["coverpage"].find_one(
                {"subject": subject, "exp_no": exp_no, "group": group},
                sort=[("generated_at", -1)]   # most recent first
            )
        → returns {"1": record_or_None, "2": record_or_None}
    ↓
    For each group with a record:
        formats display date: _display_date(iso) → "dd-mm-yyyy"
        builds InlineKeyboardButton:
            label: "📌 1st 30: 19-07-2026, 26-07-2026"
            callback_data: "coverpage:dates:{ISO_exp},{ISO_sub}"
    ↓
    Appends footer row: [🌐 Official][❌ Cancel]
    ↓
    Builds prompt text with hint if buttons exist
    Returns (prompt_text, InlineKeyboardMarkup)
```

**Path A — Quick Select (tap a date button):**

```
User taps "📌 1st 30: 19-07-2026, 26-07-2026"
    ↓
coverpage.py :: cp_dates_quick_select(update, context)
    → extracts payload: "YYYY-MM-DD,YYYY-MM-DD" from callback_data
    → splits into exp_date_iso, sub_date_iso
    ↓
    Loads student data, teacher info, subject metadata
    Builds full config dict (same structure as manual path)
    ↓
    → calls generate_from_dict(config, out_path)  [see PDF generation below]
    → sends PDF
    → saves record to coverpage collection
    → returns ConversationHandler.END
```

**Path B — Manual date typed:**

```
User types: "19-07-2026, 26-07-2026"
    ↓
coverpage.py :: cp_receive_dates(update, context)
    ↓
    _parse_dates_input(text)
        → re.split(r"\s*,\s*", text)
        → _parse_date(part) for each:
            datetime.strptime(raw, "%d-%m-%Y") or "%d/%m/%Y"
            returns ISO "YYYY-MM-DD"
        → returns (exp_date_iso, sub_date_iso)
    ↓
    If invalid → reply error, return ENTER_DATES (stay in state)
    ↓
    If valid → same generation pipeline as quick-select path
```

---

#### PDF Generation Pipeline

```
coverpage.py (cp_receive_dates or cp_dates_quick_select)
    ↓
    Assembles config dict:
    {
        "department":         "Electrical & Electronic Engineering",
        "type":               "Lab Report",
        "courseNo":           "EEE - 2152",
        "courseTitle":        "Electrical Circuits II",
        "coverNo":            "3",
        "coverTitle":         "Kirchhoff's Laws",
        "teacherName":        "Dr. Teacher Name",
        "teacherDesignation": "Professor",
        "teacherDepartment":  "EEE",
        "dateOfExperiment":   "2026-07-19",
        "dateOfSubmission":   "2026-07-26",
        "watermark": False, "courseCode": False,
        "studentSession": True, "assessmentTable": False,
        "students": [{"id": "2403042", "name": "...", "section": "C"}]
    }
    ↓
    asyncio.get_running_loop().run_in_executor(
        None,
        generate_from_dict,    # ← coverpage/generate.py
        config,
        out_path               # coverpage/generated_covers/{roll}_{name}_Exp{n}_{subject}.pdf
    )
    ↓
    coverpage/generate.py :: generate_from_dict(cfg, out_path)
        → creates FPDF instance (A4, portrait)
        → adds fonts: TeXGyreTermes-Regular.ttf, Bold.ttf
        → draws:
            RUET logo (PNG, left)
            Motto image (PNG, right)
            Department header, divider lines
            Type badge (Lab Report / Assignment)
            Course No + Title
            Experiment No + Title
            Teacher info table
            Student info table (roll, name, section, session)
            Date row (experiment date | submission date)
        → pdf.output(out_path)
    ↓
    open(out_path, "rb") → update.message.reply_document(...)
    ↓
    os.remove(out_path)   # cleanup
    ↓
    database.py :: save_coverpage_record(user_id, roll, subject, exp_no, group, exp_date, sub_date)
        → db["coverpage"].insert_one({...})
```

---

### Admin Panel

**Trigger:** Admin sends `/admin`

```
command.py :: admin(update, context)
    → checks: update.effective_user.id in config.admin_list.values()
    → if not admin: reply "Sorry, You are not an admin"
    → if admin: reply with admin_keyboard (defined in command.py)
```

**Admin button callbacks** are all handled by `inline_button.py :: admin_button_handler()`:

| Callback | Function called | What it does |
|---|---|---|
| `admin:routine_update` | `threading.Thread(target=update_routine)` | Calls `web_screenshot.py` to screenshot routine URLs, saves to `resources/routine/*.png` |
| `admin:routine_toggle` | Shows confirm keyboard | — |
| `admin:toggle_routine:confirm` | `routine.py :: toggle_routine()` | Flips week in local JSON + inserts new doc to MongoDB `routine_week_selector` |
| `admin:circulate_routine` | `routine.py :: circulate_routine()` | Reads user_data.json, sends photo to every user_id |
| `admin:circulate_schedule` | `schedule.py :: circulate_schedule()` | Reads user_data.json, calls get_schedule(), sends text to every user_id |
| `admin:show_user` | `inline_button.py :: list_user()` | Reads user_data.json, returns `"roll : user_id\n"` for each registered user |
| `admin:cancel` | — | Edits message to "Request Cancelled" |

---

### Notice Broadcast Conversation

**Trigger:** Admin taps "Publish Notice" in the admin panel (`callback_data="admin:notice"`)

**ConversationHandler states:** `recieve_notice`

```
Callback: "admin:notice"
    ↓
conversation.py :: ask_for_notice(update, context)
    → query.answer()
    → edit message: "Please Enter the notice:"
    → returns state "recieve_notice"
    ↓
Admin types notice text
    ↓
conversation.py :: recieve_notice(update, context)
    ↓
    reads .data/user_data.json
    collects all user_ids where user_id is not None
    ↓
    for each user_id:
        context.bot.send_message(
            chat_id=user_id,
            text="NOTICE:\n\n" + text
        )
        count += 1
        edit progress message
    ↓
    final edit: "The notice is circulated to N people."
    → returns ConversationHandler.END
```

---

## 🗃 Data Storage Reference

### `.data/user_data.json` — structure

```json
{
  "2403042": {
    "name": "Student Name",
    "section": "C",
    "user_id": 123456789,
    "teacher_choices": {
      "EEE 2152": "1",
      "CSE 2101": "2"
    }
  }
}
```

### `.data/subject_teachers.json` — structure

```json
{
  "EEE 2152": {
    "title": "Electrical Circuits II",
    "type": "sessional",
    "1": {
      "name": "Dr. Teacher One",
      "designation": "Professor",
      "department": "EEE"
    },
    "2": {
      "name": "Dr. Teacher Two",
      "designation": "Associate Professor",
      "department": "EEE"
    }
  }
}
```

### `.data/subject_experiments.json` — structure

```json
{
  "EEE 2152": {
    "type": "sessional",
    "experiments": {
      "1": {"type": "Lab Report", "title": "Study of Voltage Divider"},
      "2": {"type": "Lab Report", "title": "Verification of KVL"},
      "3": {"type": "Lab Report", "title": "Kirchhoff's Laws"}
    }
  }
}
```

### `.data/routine_odd_even_week.json` — structure

```json
{
  "id": "routine_week_selector",
  "week": "odd"
}
```

---

## 🗄 MongoDB Collections Reference

### `phantom_bot_db` database

**`<roll_number>` (e.g. `2403042`)**
```json
{
  "roll": "2403042",
  "name": "Student Name",
  "section": "C",
  "user_id": 123456789,
  "teacher_choices": {"EEE 2152": "1"}
}
```

**`coverpage`**
```json
{
  "user_id": 123456789,
  "roll": "2403042",
  "subject": "EEE 2152",
  "exp_no": "3",
  "group": "2",
  "date_of_experiment": "2026-07-19",
  "date_of_submission": "2026-07-26",
  "generated_at": "2026-07-19T05:30:00"
}
```

**`subject_teachers`** — mirrors `.data/subject_teachers.json` + `normalized` field for fuzzy match  
**`subject_experiments`** — mirrors `.data/subject_experiments.json` + `normalized` field  
**`routine_week_selector`** — `{id, week}`

### `schedule` database

Collections: `ct`, `assignment`, `semester_final`, `backlog`

Each document:
```json
{
  "subject": "EEE 2152",
  "teacher": "Dr. Name",
  "date": "2026-07-25",
  "time": "10:00 AM",
  "topic": "Chapter 1-3",
  "syllabus": "KVL, KCL"
}
```

---

## 📊 File Dependency Graph

```
bot/main.py
  └─ bot/bot.py
       ├─ config.py  (env vars, keyboards, paths, MongoDB client)
       ├─ bot/handlers/command.py
       │    └─ config.py
       ├─ bot/handlers/message.py
       │    ├─ config.py
       │    ├─ bot/services/routine.py
       │    │    ├─ config.py
       │    │    ├─ bot/scripts/web_screenshot.py
       │    │    ├─ bot/services/storage.py  ← reads .data/*.json
       │    │    └─ bot/services/database.py
       │    └─ bot/services/schedule.py
       │         └─ config.py (MongoDB client)
       ├─ bot/handlers/conversation.py
       │    ├─ config.py
       │    ├─ bot/services/database.py
       │    └─ bot/scripts/yt_downloader.py
       ├─ bot/handlers/inline_button.py
       │    ├─ config.py
       │    ├─ bot/services/routine.py
       │    ├─ bot/services/schedule.py
       │    └─ bot/scripts/yt_downloader.py
       └─ bot/handlers/coverpage.py
            ├─ config.py
            ├─ bot/services/database.py
            │    ├─ save_coverpage_record()
            │    ├─ get_coverpage_dates_by_group()
            │    ├─ get_subject_experiments()
            │    ├─ add_experiment_to_subject()
            │    └─ save_user_teacher_choice()
            └─ coverpage/generate.py
                 └─ coverpage/assets/  (fonts, images)
```

---

## 🔧 Key Utility Functions

### `coverpage.py`

| Function | Purpose |
|---|---|
| `_get_student_by_user_id(user_id)` | Scans user_data.json, returns `(roll, data)` or `(None, None)` |
| `_get_student_group(roll)` | Returns `"1"` or `"2"` based on roll suffix, cycling every 60 |
| `_get_teacher(subject, roll, teacher_key)` | Returns teacher dict from subject_teachers.json |
| `_parse_date(raw)` | Accepts `dd-mm-yyyy` or `dd/mm/yyyy`, returns ISO `yyyy-mm-dd` |
| `_parse_dates_input(text)` | Splits comma-separated date pair, returns two ISO dates |
| `_display_date(iso)` | Converts `yyyy-mm-dd` → `dd-mm-yyyy` for display |
| `_build_subject_keyboard(subjects)` | Builds 2-per-row InlineKeyboardMarkup |
| `_build_experiment_keyboard(experiments)` | Builds one-per-row experiment keyboard |
| `_build_date_ui(context, user_id)` | Fetches historical dates from MongoDB, builds quick-select keyboard |
| `_transition_to_experiment_step(query, context, subject)` | Bridges teacher→experiment step |

### `database.py`

| Function | Purpose |
|---|---|
| `load_data()` | Calls all 5 load functions on startup |
| `load_users()` | MongoDB → `.data/user_data.json` |
| `load_subject_teachers()` | MongoDB (with auto-seed) → `.data/subject_teachers.json` |
| `load_subject_experiments()` | MongoDB (with auto-seed) → `.data/subject_experiments.json` |
| `load_routine_odd_even_sequence()` | MongoDB → `.data/routine_odd_even_week.json` |
| `load_teacher_data()` | HTTP API → `.data/teacher_data.json` |
| `save_coverpage_record(...)` | Inserts cover page history record |
| `get_coverpage_dates_by_group(subject, exp_no)` | Returns most recent dates per roll group |
| `get_subject_experiments(subject_name)` | Finds experiment doc by normalized subject name |
| `add_experiment_to_subject(...)` | Upserts new experiment into the experiments collection |
| `save_user_teacher_choice(roll, subject, teacher_key)` | Saves teacher choice to MongoDB + local JSON |

### `routine.py`

| Function | Purpose |
|---|---|
| `is_even_week()` | Returns `(bool, activation_date_str)` using calibration date math |
| `update_routine()` | Takes screenshots of both routine URLs, saves to `resources/routine/` |
| `toggle_routine()` | Flips odd/even week state in JSON + MongoDB |
| `circulate_routine(update, context)` | Sends routine photo to all active users |

### `schedule.py`

| Function | Purpose |
|---|---|
| `get_schedule()` | Queries MongoDB `schedule` db, builds formatted Markdown string |
| `circulate_schedule(update, context)` | Sends schedule text to all active users |

### `storage.py`

| Function | Purpose |
|---|---|
| `get_user_data()` | Reads and returns `.data/user_data.json` |
| `get_routine_week()` | Reads `.data/routine_odd_even_week.json`, returns `"odd"` or `"even"` |

### `inline_button.py`

| Function | Purpose |
|---|---|
| `admin_button_handler(update, context)` | Routes all `admin:*` callbacks |
| `resources_button_handler(update, context)` | Routes all `resources:*` callbacks |
| `syllabus_id_handler(update, context)` | Sends the actual syllabus PDF file |
| `yt_download_file_id_handler(update, context)` | Starts the YT download for the chosen format |
| `list_user()` | Returns formatted string of roll → user_id pairs |
