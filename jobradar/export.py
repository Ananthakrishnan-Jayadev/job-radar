"""CSV export of jobs, with the same filters as search."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from . import db
from .models import size_band

COLUMNS = [
    "company", "title", "location", "provinces", "workplace", "posted_at", "salary",
    "status", "applied_at", "notes", "company_size", "system", "first_seen", "last_seen",
    "closed_at", "url",
]


def export_jobs(
    conn: sqlite3.Connection,
    path: Path | str,
    *,
    query: str | None = None,
    provinces: list[str] | None = None,
    include_closed: bool = False,
) -> int:
    """Write matching jobs to *path*. Returns the number of rows written."""
    rows = db.find_jobs(conn, query, provinces=provinces, include_closed=include_closed)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "company": r["company"],
                "title": r["title"],
                "location": db.location_label(r["locations"]),
                "provinces": ",".join(sorted({l.province for l in r["locations"] if l.in_canada and l.province})),
                "workplace": r["workplace"],
                "posted_at": r["posted_at"] or "",
                "salary": r["salary_text"] or "",
                "status": r["status"],
                "applied_at": r["applied_at"] or "",
                "notes": r["notes"],
                "company_size": size_band(r["employee_count"]),
                "system": r["system"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "closed_at": r["closed_at"] or "",
                "url": r["url"],
            })
    return len(rows)
