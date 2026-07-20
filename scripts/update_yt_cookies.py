#!/usr/bin/env python3
"""Copy YouTube-relevant browser cookies into the Phantom_bot project for yt-dlp."""

import os
import shutil
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKIES_DIR = PROJECT_ROOT / "cookies"
HOME = Path.home()

SOURCE_ROOTS = {
    "zen": [
        HOME / ".config" / "zen",
    ],
    "firefox-developer-edition": [
        HOME / ".mozilla" / "firefox-developer-edition",
        HOME / ".config" / "firefox-developer-edition",
        HOME / ".var" / "app" / "org.mozilla.firefox-developer-edition" / ".mozilla" / "firefox-developer-edition",
    ],
}


def newest_cookie_db(roots):
    dbs = []
    for root in roots:
        if not root.exists():
            continue
        dbs.extend(root.rglob("cookies.sqlite"))
    if not dbs:
        return None
    return max(dbs, key=lambda p: p.stat().st_mtime)


def copy_raw_db(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    for suffix in ("-wal", "-shm"):
        side = src.with_name(src.name + suffix)
        if side.exists():
            shutil.copy2(side, dest.with_name(dest.name + suffix))


def checkpoint_copy(dest: Path) -> None:
    with sqlite3.connect(dest) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("PRAGMA journal_mode=DELETE;")


def copy_sidecar_files(src: Path, dest_dir: Path) -> None:
    for name in ("containers.json",):
        side = src.parent / name
        if side.exists():
            shutil.copy2(side, dest_dir / name)


def main() -> int:
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    copied = []

    for label, roots in SOURCE_ROOTS.items():
        db = newest_cookie_db(roots)
        dest_dir = COOKIES_DIR / label

        if db is None:
            print(f"[skip] {label}: no cookies.sqlite found")
            continue

        try:
            copy_raw_db(db, dest_dir / "cookies.sqlite")
            try:
                checkpoint_copy(dest_dir / "cookies.sqlite")
            except Exception as exc:
                print(f"[warn] {label}: could not checkpoint copy ({exc})")
            copy_sidecar_files(db, dest_dir)
            copied.append(label)
            print(f"[ok] {label}: {db} -> {dest_dir / 'cookies.sqlite'}")
        except Exception as exc:
            print(f"[error] {label}: copy failed ({exc})")

    os.chmod(COOKIES_DIR, 0o700)
    for child in COOKIES_DIR.iterdir():
        if child.is_dir():
            os.chmod(child, 0o700)

    print(f"Cookies dir: {COOKIES_DIR}")
    return 0 if copied else 1


if __name__ == "__main__":
    raise SystemExit(main())
