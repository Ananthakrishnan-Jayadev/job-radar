"""What the user changes by hand: statuses, notes, sizes, boards, saved searches.

Rules:
- Changing a job's status records it in job_events and sets status_changed_at.
- The first move to "applied" sets applied_at to today unless one is given.
- A manual employee count always wins over other sources (size_source "manual").
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from . import db
from .models import COMPANY_STATUSES, JOB_STATUSES

UNSET = object()  # "not given", as opposed to None ("clear it")

VISIT_GAP = timedelta(hours=1)


class NotFoundError(LookupError):
    pass


class InvalidValue(ValueError):
    pass


def update_job(conn: sqlite3.Connection, job_id: int, *, status=UNSET, notes=UNSET, applied_at=UNSET) -> dict:
    row = conn.execute("SELECT status, applied_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"job {job_id} not found")
    stamp = db.now()
    with conn:
        if status is not UNSET and status != row["status"]:
            if status not in JOB_STATUSES:
                raise InvalidValue(f"unknown status {status!r}")
            conn.execute("UPDATE jobs SET status = ?, status_changed_at = ? WHERE id = ?", (status, stamp, job_id))
            conn.execute("INSERT INTO job_events (job_id, at, field, old, new) VALUES (?, ?, 'status', ?, ?)",
                         (job_id, stamp, row["status"], status))
            if status == "applied" and row["applied_at"] is None and applied_at is UNSET:
                conn.execute("UPDATE jobs SET applied_at = ? WHERE id = ?", (stamp[:10], job_id))
        if notes is not UNSET:
            conn.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes or "", job_id))
        if applied_at is not UNSET:
            conn.execute("UPDATE jobs SET applied_at = ? WHERE id = ?", (applied_at or None, job_id))
    return dict(conn.execute("SELECT id, status, notes, applied_at, status_changed_at FROM jobs WHERE id = ?",
                             (job_id,)).fetchone())


def job_events(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT at, field, old, new FROM job_events WHERE job_id = ? ORDER BY id", (job_id,))]


def update_company(conn: sqlite3.Connection, company_id: int, *, status=UNSET, notes=UNSET,
                   employee_count=UNSET, canadian=UNSET, careers_url=UNSET) -> None:
    if conn.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
        raise NotFoundError(f"company {company_id} not found")
    with conn:
        if status is not UNSET:
            if status not in COMPANY_STATUSES:
                raise InvalidValue(f"unknown company status {status!r}")
            conn.execute("UPDATE companies SET status = ? WHERE id = ?", (status, company_id))
        if notes is not UNSET:
            conn.execute("UPDATE companies SET notes = ? WHERE id = ?", (notes or "", company_id))
        if employee_count is not UNSET:
            if employee_count is not None and employee_count < 0:
                raise InvalidValue("employee count can't be negative")
            conn.execute(
                "UPDATE companies SET employee_count = ?, size_source = ?, size_updated_at = ? WHERE id = ?",
                (employee_count, "manual" if employee_count is not None else None, db.now(), company_id),
            )
        if canadian is not UNSET:
            conn.execute("UPDATE companies SET canadian = ? WHERE id = ?", (int(bool(canadian)), company_id))
        if careers_url is not UNSET:
            conn.execute("UPDATE companies SET careers_url = ? WHERE id = ?", (careers_url or None, company_id))


def update_board(conn: sqlite3.Connection, board_id: int, *, enabled=UNSET, confirmed=UNSET) -> None:
    if conn.execute("SELECT 1 FROM boards WHERE id = ?", (board_id,)).fetchone() is None:
        raise NotFoundError(f"board {board_id} not found")
    with conn:
        if enabled is not UNSET:
            conn.execute("UPDATE boards SET enabled = ? WHERE id = ?", (int(bool(enabled)), board_id))
        if confirmed is not UNSET:
            conn.execute("UPDATE boards SET confirmed = ? WHERE id = ?", (int(bool(confirmed)), board_id))


# --- saved searches ------------------------------------------------------------------

def list_saved_searches(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM saved_searches ORDER BY name COLLATE NOCASE").fetchall()
    return [{**dict(r), "filters": json.loads(r["filters"]), "use_for_sources": bool(r["use_for_sources"])}
            for r in rows]


def save_search(conn: sqlite3.Connection, name: str, query: str, filters: dict, use_for_sources: bool) -> int:
    name = name.strip()
    if not name:
        raise InvalidValue("a saved search needs a name")
    with conn:
        conn.execute(
            """
            INSERT INTO saved_searches (name, query, filters, use_for_sources) VALUES (?, ?, ?, ?)
            ON CONFLICT (name) DO UPDATE SET query = excluded.query, filters = excluded.filters,
                                             use_for_sources = excluded.use_for_sources
            """,
            (name, query or "", json.dumps(filters or {}), int(use_for_sources)),
        )
    return conn.execute("SELECT id FROM saved_searches WHERE name = ?", (name,)).fetchone()[0]


def update_saved_search(conn: sqlite3.Connection, search_id: int, *, use_for_sources=UNSET, name=UNSET) -> None:
    if conn.execute("SELECT 1 FROM saved_searches WHERE id = ?", (search_id,)).fetchone() is None:
        raise NotFoundError(f"saved search {search_id} not found")
    with conn:
        if use_for_sources is not UNSET:
            conn.execute("UPDATE saved_searches SET use_for_sources = ? WHERE id = ?",
                         (int(bool(use_for_sources)), search_id))
        if name is not UNSET:
            if not (name or "").strip():
                raise InvalidValue("a saved search needs a name")
            conn.execute("UPDATE saved_searches SET name = ? WHERE id = ?", (name.strip(), search_id))


def delete_saved_search(conn: sqlite3.Connection, search_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))


# --- "new since last visit" -------------------------------------------------------------

def record_visit(conn: sqlite3.Connection, at: datetime | None = None) -> str | None:
    """Note a visit; return the time of the previous visit, or None for the first.

    Opens within an hour of each other count as one visit, so reloading the page
    doesn't clear the "new" markers.
    """
    at = at or datetime.now(UTC)
    last_seen = db.get_setting(conn, "last_seen_at")
    baseline = db.get_setting(conn, "visit_baseline")
    if last_seen is None or at - datetime.fromisoformat(last_seen) > VISIT_GAP:
        baseline = last_seen
        db.set_setting(conn, "visit_baseline", baseline)
    db.set_setting(conn, "last_seen_at", at.replace(microsecond=0).isoformat())
    return baseline
