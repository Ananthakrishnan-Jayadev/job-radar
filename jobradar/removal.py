"""Taking companies off the list, without losing them for good.

Removing a company deletes it with its boards and jobs. Before that, they are
copied into data/removed-companies-YYYYMMDD-HHMMSS.db (the same format as the
main database, holding only those companies), as the 2026-10-27 cleanup did,
so a company removed by mistake can be looked up or brought back.

A company with a tracked job (a status other than Not reviewed, notes, or an
applied date) is kept unless removing tracked companies is asked for: that
tracking is the one thing a scan can't rebuild.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from . import db

PREFIX = "removed-companies-"

_TRACKED = "(j.status <> 'new' OR j.notes <> '' OR j.applied_at IS NOT NULL)"


def _marks(ids: list[int]) -> str:
    return ",".join("?" * len(ids))


def tracked_jobs(conn: sqlite3.Connection, company_ids: list[int]) -> dict[int, int]:
    """How many tracked jobs each of these companies has (companies with none are left out)."""
    if not company_ids:
        return {}
    rows = conn.execute(
        f"""SELECT b.company_id, COUNT(*) FROM jobs j JOIN boards b ON b.id = j.board_id
            WHERE b.company_id IN ({_marks(company_ids)}) AND {_TRACKED}
            GROUP BY b.company_id""",
        company_ids,
    )
    return {company: count for company, count in rows}


def _archive(conn: sqlite3.Connection, ids: list[int], folder: Path) -> Path:
    """Copy these companies, their boards, jobs, locations and job history into a new file."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = PREFIX + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path, n = folder / f"{stamp}.db", 1
    while path.exists():  # two removals in the same second
        n += 1
        path = folder / f"{stamp}-{n}.db"
    db.connect(path).close()  # an empty database at the current schema
    marks = _marks(ids)
    jobs = f"SELECT j.id FROM main.jobs j JOIN main.boards b ON b.id = j.board_id WHERE b.company_id IN ({marks})"
    conn.execute("ATTACH DATABASE ? AS archive", (str(path),))
    try:
        with conn:
            conn.execute(f"INSERT INTO archive.companies SELECT * FROM main.companies WHERE id IN ({marks})", ids)
            conn.execute(f"INSERT INTO archive.boards SELECT * FROM main.boards WHERE company_id IN ({marks})", ids)
            conn.execute(f"INSERT INTO archive.jobs SELECT * FROM main.jobs WHERE id IN ({jobs})", ids)
            conn.execute(f"INSERT INTO archive.job_locations SELECT * FROM main.job_locations WHERE job_id IN ({jobs})", ids)
            conn.execute(f"INSERT INTO archive.job_events SELECT * FROM main.job_events WHERE job_id IN ({jobs})", ids)
    except sqlite3.Error:
        conn.execute("DETACH DATABASE archive")
        path.unlink(missing_ok=True)
        raise
    conn.execute("DETACH DATABASE archive")
    return path


def remove_companies(conn: sqlite3.Connection, company_ids: list[int], folder: Path | str, *,
                     include_tracked: bool = False) -> dict:
    """Archive, then delete, these companies with their boards and jobs.

    Returns what was removed, what was kept because it has tracked jobs, how
    many jobs went, and the archive file (None when nothing was removed).
    """
    ids = sorted(set(company_ids))
    found = {row["id"]: row["name"] for row in conn.execute(
        f"SELECT id, name FROM companies WHERE id IN ({_marks(ids)})", ids)} if ids else {}
    tracked = tracked_jobs(conn, list(found))
    kept = [] if include_tracked else [i for i in found if tracked.get(i)]
    gone = [i for i in found if i not in kept]

    archive = None
    jobs = 0
    if gone:
        jobs = conn.execute(
            f"SELECT COUNT(*) FROM jobs j JOIN boards b ON b.id = j.board_id WHERE b.company_id IN ({_marks(gone)})",
            gone,
        ).fetchone()[0]
        archive = _archive(conn, gone, Path(folder))
        with conn:
            conn.execute(f"DELETE FROM companies WHERE id IN ({_marks(gone)})", gone)
    return {
        "removed": [{"id": i, "name": found[i]} for i in gone],
        "kept": [{"id": i, "name": found[i], "tracked": tracked[i]} for i in kept],
        "jobs": jobs,
        "archive": archive.name if archive else None,
    }
