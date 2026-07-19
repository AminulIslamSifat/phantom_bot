# 🤖 Phantom Bot

> A feature-rich Telegram bot for **RUET CSE Section-C** students.  
> Routine delivery, academic schedule tracking, resource sharing, and automated cover page generation — all in one place.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Environment Variables](#-environment-variables)
- [Running the Bot](#-running-the-bot)
- [Admin Panel](#-admin-panel)
- [Database Design](#-database-design)
- [Cover Page System](#-cover-page-system)
- [Deployment](#-deployment)
- [Documentation](#-documentation)

---

## 🌟 Overview

Phantom Bot is a purpose-built Telegram bot that serves the students of **RUET CSE Section-C**. Instead of searching WhatsApp groups for the latest routine or scrambling before exams for class schedules, students get everything they need through a single Telegram interface.

The bot handles:
- Smart **routine delivery** (odd/even week aware)
- Live **exam & CT schedule** with countdown timers
- **Resource sharing** (syllabus PDFs, Google Drive links, classroom codes)
- **YouTube video downloading** via yt-dlp + Telegram upload
- Fully automated **RUET-standard cover page generation** as a PDF

---

## ✨ Features

| Feature | Description |
|---|---|
| 📅 **Routine** | Sends the correct odd/even week routine image automatically |
| 📆 **Schedule** | Live CT, Assignment, Semester Final schedule with countdown timers |
| 📁 **Resources** | Syllabus PDFs, Google Drive folders, classroom codes, CSE Archive |
| 📥 **YT Downloader** | Download YouTube videos in multiple qualities and upload to Telegram |
| 📄 **Cover Page** | Generate RUET-standard PDF cover pages for lab reports and assignments |
| 🔔 **Broadcast** | Admin can push notices, routines, and schedules to all registered users |
| 🔐 **Registration** | Roll-based student registration tied to Telegram user ID |
| 👥 **Admin Panel** | Full admin control panel with inline keyboard |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Bot Framework** | python-telegram-bot v21 |
| **Database** | MongoDB Atlas (via PyMongo) |
| **Userbot Client** | Telethon (for YT upload to Telegram) |
| **PDF Generation** | fpdf2 + Pillow |
| **Video Download** | yt-dlp |
| **Web Server** | aiohttp (health check endpoint) |
| **Package Manager** | `uv` |

---

## 🗂 Project Structure

```
phantom_bot/
├── bot/
│   ├── bot.py                  # Application setup, all handler registration
│   ├── main.py                 # Entry point: loads data, starts polling + health server
│   ├── handlers/
│   │   ├── command.py          # /start, /admin, /help commands
│   │   ├── message.py          # Reply-keyboard message routing (Routine, Schedule, Resources, Cover Page)
│   │   ├── conversation.py     # Multi-step conversations (YT downloader, Registration, Notice)
│   │   ├── inline_button.py    # Callback query handlers (admin, resources, syllabus, YT)
│   │   └── coverpage.py        # Full 5-step cover page conversation flow
│   ├── services/
│   │   ├── database.py         # All MongoDB operations + local JSON cache management
│   │   ├── routine.py          # Routine screenshot, toggle, and circulation logic
│   │   ├── schedule.py         # Schedule fetching and circulation
│   │   └── storage.py          # Simple local JSON file reads
│   └── scripts/
│       ├── yt_downloader.py    # yt-dlp format detection and async download
│       └── web_screenshot.py   # Web screenshot capture for routine images
├── coverpage/
│   ├── generate.py             # FPDF2-based PDF cover page renderer
│   ├── assets/                 # Fonts (TeXGyreTermes), RUET logo, motto image
│   └── generated_covers/       # Temporary output directory (auto-cleaned after send)
├── resources/
│   ├── routine/                # Cached routine PNG images (odd/even week)
│   └── syllabus/
│       ├── official/           # Official RUET syllabus PDFs
│       └── unofficial/         # Manually created syllabus PDFs
├── .data/                      # Runtime JSON cache (git-ignored, rebuilt on startup)
│   ├── user_data.json
│   ├── subject_teachers.json
│   ├── subject_experiments.json
│   ├── teacher_data.json
│   ├── routine_odd_even_week.json
│   └── tmp/                    # Temporary YT download files
├── config.py                   # All config, env loading, global keyboards, paths
├── pyproject.toml
└── .env                        # Secret keys (never commit this)
```

---

## ✅ Prerequisites

- Python **3.11+**
- `uv` package manager (`pip install uv`)
- A MongoDB Atlas cluster
- A Telegram Bot Token (from @BotFather)
- A Telethon session string (for YT uploader)
- A Screenshot API key (for routine image capture)

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/AminulIslamSifat/phantom_bot
cd phantom_bot

# Create virtual environment and install dependencies
uv sync

# Copy and fill in environment variables
cp .env.example .env
nano .env
```

---

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `IS_LOCAL` | `True` to use test bot token, `False` for production |
| `TELEGRAM_BOT_TOKEN` | Production bot token |
| `TELEGRAM_BOT_TOKEN_TEST` | Test/dev bot token |
| `MONGODB_USERNAME` | MongoDB Atlas username |
| `MONGODB_USER_PASSWORD` | MongoDB Atlas password |
| `SCREENSHOT_API` | API key for web screenshot service |
| `TELETHON_API_ID` | Telethon App ID |
| `TELETHON_API_HASH` | Telethon App Hash |
| `TELETHON_SESSION` | Production Telethon session string |
| `TELETHON_SESSION_TEST` | Test Telethon session string |
| `PHANTOM_BOT_CHANNEL_ID` | Telegram channel ID for YT uploads |
| `MAX_DOWNLOAD_SIZE_MB` | Max video download size (default: 500) |
| `USE_WEBHOOK` | Set to `False` for polling mode |
| `PORT` | Health server port (default: 8000) |

---

## 🚀 Running the Bot

```bash
# Run with uv (recommended)
uv run python -m bot.main

# Or activate venv manually
source .venv/bin/activate
python -m bot.main
```

On startup, the bot:
1. Calls `load_data()` — syncs all MongoDB data to `.data/` JSON caches
2. Starts the aiohttp health-check server on `PORT`
3. Begins Telegram polling

---

## 🔧 Admin Panel

Access with `/admin` command (whitelisted Telegram IDs in `config.admin_list`).

| Button | Action |
|---|---|
| Update Routine | Screenshots the live routine website, caches as PNG |
| Edit Routine | Opens the routine editor web app (URL button) |
| Toggle Routine | Flips the odd/even week baseline in MongoDB |
| Circulate Routine | Sends the current routine image to all registered users |
| Edit Schedule | Opens the schedule editor web app |
| Circulate Schedule | Pushes the current schedule text to all registered users |
| Edit Subject Teacher Data | Opens the teacher data editor |
| Edit Experiment/Assignment | Opens the experiment list editor |
| Publish Notice | Broadcasts a custom text message to all registered users |
| Show User | Lists all registered roll numbers with Telegram user IDs |

---

## 🗃 Database Design

### MongoDB — `phantom_bot_db`

| Collection | Document structure |
|---|---|
| `<roll_number>` | `{roll, name, section, user_id, teacher_choices: {subject: key}}` |
| `routine_week_selector` | `{id: "routine_week_selector", week: "odd"/"even"}` |
| `subject_teachers` | `{subject, normalized, title, type, "1": {name, designation, department}, "2": {...}}` |
| `subject_experiments` | `{subject, normalized, type, experiments: {exp_no: {type, title}}}` |
| `coverpage` | `{user_id, roll, subject, exp_no, group, date_of_experiment, date_of_submission, generated_at}` |

### MongoDB — `schedule`

| Collection | Purpose |
|---|---|
| `ct` | Class test schedules |
| `assignment` | Assignment deadlines |
| `semester_final` | Semester final exam dates |
| `backlog` | Backlog exam schedule |

### Local Cache — `.data/`

JSON files mirroring MongoDB for fast startup reads. Automatically rebuilt by `load_data()` on every bot start.

---

## 📄 Cover Page System

Generates RUET-standard PDF lab report / assignment cover pages on demand.

**5-step conversation flow:**
1. **Subject selection** — choose from subject list
2. **Teacher selection** — one-time choice saved permanently per student
3. **Experiment selection** — pick from list or enter manually
4. **Date entry** — tap a quick-select button from history or type `dd-mm-yyyy, dd-mm-yyyy`
5. **PDF generation** — sent to user, deleted from disk, logged to MongoDB

---

## ☁️ Deployment

Designed for **Railway**, **Render**, or any VPS with Python support.

```bash
# Health check
GET / → 200 "ok"
```


---

## 📚 Documentation

| Document | Description |
|---|---|
| [user_guide.md](user_guide.md) | End-user guide — how to use every feature of the bot |
| [developer_helper.md](developer_helper.md) | Developer reference — full flow diagrams, function map, data schemas |

