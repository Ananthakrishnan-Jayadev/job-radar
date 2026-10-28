"""Dated copies of the database, safe to take while the app is running.

Your tracking (statuses, notes, applied dates) is the one thing a scan can't
rebuild, so the app reminds you when the newest copy is older than
REMIND_AFTER_DAYS.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

PREFIX = "jobradar-backup-"
REMIND_AFTER_DAYS = 7
_STAMP = re.compile(rf"^{PREFIX}(\d{{8}}-\d{{6}})")


class BackupError(Exception):
    pass


def make_backup(conn: sqlite3.Connection, folder: Path | str, *, note: str = "") -> Path:
    """Copy the database into *folder* as jobradar-backup-YYYYMMDD-HHMMSS[-note].db
    and check the copy opens cleanly. Uses SQLite's online backup, so a scan or
    the web app can keep running."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = PREFIX + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if note:
        name += "-" + re.sub(r"[^a-z0-9]+", "-", note.lower()).strip("-")
    path = folder / f"{name}.db"
    if path.exists():
        raise BackupError(f"{path} already exists; try again in a second")
    copy = sqlite3.connect(path)
    try:
        conn.backup(copy)
        ok = copy.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copy.close()
    if ok != "ok":
        path.unlink(missing_ok=True)
        raise BackupError(f"the copy failed its integrity check: {ok}")
    return path


def latest_backup(folder: Path | str) -> tuple[Path, datetime] | None:
    """The newest backup in *folder* and when it was taken (UTC), or None."""
    found = []
    for path in Path(folder).glob(f"{PREFIX}*.db"):
        if m := _STAMP.match(path.name):
            found.append((datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=UTC), path))
    if not found:
        return None
    taken, path = max(found)
    return path, taken


def backup_status(folder: Path | str, now: datetime | None = None) -> dict:
    """For the web app: the newest backup, its age in days, and whether to remind."""
    now = now or datetime.now(UTC)
    latest = latest_backup(folder)
    if latest is None:
        return {"latest": None, "taken_at": None, "age_days": None, "remind": True}
    path, taken = latest
    age = (now - taken).days
    return {"latest": path.name, "taken_at": taken.isoformat(), "age_days": age, "remind": age >= REMIND_AFTER_DAYS}
