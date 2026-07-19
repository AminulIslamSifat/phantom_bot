# 📖 Phantom Bot — User Guide

---

## Getting Started

Send `/start` → if not registered, tap **Register** → enter your **7-digit roll number**.  
That's it. You're in. 🎉

---

## Main Menu

After registration you'll see 4 buttons at the bottom:

```
[ Routine  ]  [ Schedule   ]
[ Cover Page ]  [ Resources ]
```

---

## Routine

Tap **Routine** → get the current week's class routine as an image.  
Tap **Live Routine** in the message to open the web version.

---

## Schedule

Tap **Schedule** → get all upcoming CTs, assignments, and exams with countdowns like `(3d left)` or `(Today)`.

---

## Resources

Tap **Resources** → pick what you need:

- **Drive** — Google Drive links for each semester
- **Syllabus** — Official or unofficial syllabus PDFs
- **YT-downloader** — Paste a YouTube link, pick a quality, get the video in Telegram
- **CSE Archive** — Opens the RUET CSE archive website
- **G. Classroom Code** — Google Classroom join codes

---

## Cover Page Generator

Tap **Cover Page** → the bot walks you through 4 quick steps:

**1. Pick your subject**

**2. Pick your teacher** *(first time only — saved forever after that)*

**3. Pick your experiment** — or tap **✏️ Enter Manually** and type:
```
3 : Kirchhoff's Laws
```
> Manually entered experiments are **saved for everyone** — next time it shows as a button.

**4. Enter dates** — type experiment date and submission date:
```
19-07-2026, 26-07-2026
```
(experiment date first, submission date second)

> **Shortcut:** If someone in your group already generated this cover page, their dates appear as buttons — just tap to use instantly.

### Groups — 1st 30 / 2nd 30

Your roll number determines which group you're in:
- **1st 30** → rolls ending 001–030, 061–090, 121–150...
- **2nd 30** → rolls ending 031–060, 091–120, 151–180...

When a button shows `📌 1st 30: 19-07-2026, 26-07-2026`, those are the dates used by someone from that group for this exact experiment. Pick the one that matches your group.

After dates are confirmed → the bot generates and sends you a **PDF cover page** instantly. ✅

---

## Cancelling

Every screen has an **❌ Cancel** button. Tap it anytime to exit.

---

## Quick Error Reference

| What happened | Fix |
|---|---|
| "Please register" on /start | Send `/start`, tap Register, enter your roll |
| Invalid date format error | Use `dd-mm-yyyy, dd-mm-yyyy` exactly |
| Invalid experiment format | Use `exp_no : Title` with a colon |
| "Session Expired" in YT downloader | Go back to Resources → YT-downloader and paste the link again |

---

## 🔧 Admin Guide

> Only for admins listed in `config.py`. Send `/admin` to open the panel.

| Button | What it does |
|---|---|
| **Update Routine** | Refreshes the routine image from the website |
| **Toggle Routine** | Flips odd ↔ even week if it's out of sync |
| **Circulate Routine** | Sends the current routine to all registered students |
| **Edit Routine** | Opens the routine editor (web link) |
| **Edit Schedule** | Opens the schedule editor (web link) |
| **Circulate Schedule** | Sends the current schedule to all registered students |
| **Edit Subject Teacher Data** | You can edit the details of subject teacher here (web link) |
| **Edit Experiment/Assignment** | You can edit experiment/assignment details here, It will be used for cover page generation (web link) |
| **Publish Notice** | Type a message → sent to all registered students |
| **Show User** | Lists all registered roll numbers with their Telegram IDs |
| **Cancel** | Closes the panel |
