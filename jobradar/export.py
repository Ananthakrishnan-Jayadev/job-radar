"""CSV export of jobs, with the same filters as search."""

from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path
from typing import TextIO

from . import queries
from .models import size_band

COLUMNS = [
    "company", "title", "location", "provinces", "workplace", "posted_at", "salary",
    "level", "min_years", "status", "applied_at", "notes", "company_size", "system", "first_seen", "last_seen",
    "closed_at", "url",
]


def export_jobs(
    conn: sqlite3.Connection,
    path: Path | str,
    *,
    query: str | None = None,
    provinces: list[str] | None = None,
    include_closed: bool = False,
    all_roles: bool = False,
) -> int:
    """Write matching jobs to *path*. Returns the number of rows written."""
    rows = queries.find_jobs(conn, query, provinces=provinces, include_closed=include_closed, all_roles=all_roles)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        write_csv(rows, f)
    return len(rows)


def jobs_csv(conn: sqlite3.Connection, f: queries.JobFilter, sort: str | None = None) -> str:
    """CSV text for every job matching a filter (the web "Export" button)."""
    _, rows = queries.search_jobs(conn, f, sort=sort)
    out = io.StringIO()
    write_csv(rows, out)
    return out.getvalue()


def write_csv(rows: list[dict], file: TextIO) -> None:
    writer = csv.DictWriter(file, fieldnames=COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "company": r["company"],
            "title": r["title"],
            "location": queries.location_label(r["locations"]),
            "provinces": ",".join(queries.provinces_of(r["locations"])),
            "workplace": r["workplace"],
            "posted_at": r["posted_at"] or "",
            "salary": r["salary_text"] or "",
            "level": r.get("experience_level") or "",
            "min_years": "" if r.get("min_years") is None else r["min_years"],
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
