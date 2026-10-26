"""Retire Adzuna snapshot copies once the company's own board has been read.

The one-time Adzuna snapshot (docs/decisions/2026-10-26-adzuna-snapshot.md)
stored jobs with snippets only, and nothing ever refreshes or closes them.
When a company also has a confirmed board of its own and a scan reads that
board completely, its board is the better copy of every job it lists in
Canada:

- An Adzuna copy whose title matches a board job hands over its tracking
  (status, notes, applied date, status history) and is deleted.
- An Adzuna copy with no match is closed: the board no longer lists that job
  in Canada.

Board jobs are only stored when they are in Canada, so "no match" also covers
jobs the board places elsewhere.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from .locations import AMBIGUOUS_CITIES, CITIES, CITY_ALIASES, PROVINCE_CODES, PROVINCE_NAMES
from .roles import fold

SNAPSHOT_SYSTEM = "adzuna"

# Words Adzuna adds around a title: a place ("Software Engineer, AI Vancouver, BC"),
# remote/new badges, or the salary line ("CA$123K – CA$205K • Offers Equity").
_EXTRA_WORDS = (
    {"ca", "us", "usd", "cad", "new", "remote", "canada", "hybrid", "onsite", "offers", "equity", "bonus", "to"}
    | {code.lower() for code in PROVINCE_CODES}
    | {word for names in (PROVINCE_NAMES, CITIES, AMBIGUOUS_CITIES, CITY_ALIASES) for name in names
       for word in name.split()}
)
_AMOUNT = re.compile(r"^\d[\d.,]*k?$")


def same_job(snapshot_title: str, board_title: str) -> bool:
    """Is the Adzuna title the board's title, give or take Adzuna's extras?

    Strict on purpose: "Senior Software Engineer" must not match "Senior
    Software Engineer, Data Infrastructure". A miss only means the copy is
    closed instead of merged.
    """
    a, b = fold(snapshot_title), fold(board_title)
    if a == b:
        return True
    if b.strip() == "" or b not in a:
        return False
    rest = a.replace(b, " ", 1).split()
    return all(word in _EXTRA_WORDS or _AMOUNT.match(word) for word in rest)


@dataclass
class Retired:
    merged: int = 0  # copies deleted after matching a board job
    closed: int = 0  # copies the board doesn't list
    tracking_moved: int = 0  # of the merged, ones you had tracked


def retire_copies(conn: sqlite3.Connection, board_ids: Iterable[int], at: str) -> Retired:
    """Settle the Adzuna copies of companies whose confirmed boards in
    `board_ids` were just read completely and without error."""
    ids = list(board_ids)
    done = Retired()
    if not ids:
        return done
    marks = ",".join("?" * len(ids))
    companies = [r[0] for r in conn.execute(
        f"""SELECT DISTINCT b.company_id FROM boards b
            WHERE b.id IN ({marks}) AND b.system != ? AND b.confirmed = 1
              AND EXISTS (SELECT 1 FROM boards s WHERE s.company_id = b.company_id AND s.system = ?)""",
        (*ids, SNAPSHOT_SYSTEM, SNAPSHOT_SYSTEM))]
    with conn:
        for company_id in companies:
            _retire_company(conn, company_id, at, done)
    return done


def _retire_company(conn: sqlite3.Connection, company_id: int, at: str, done: Retired) -> None:
    copies = conn.execute(
        """SELECT j.id, j.title, j.status, j.notes, j.applied_at, j.status_changed_at
           FROM jobs j JOIN boards b ON b.id = j.board_id
           WHERE b.company_id = ? AND b.system = ? AND j.closed_at IS NULL""",
        (company_id, SNAPSHOT_SYSTEM)).fetchall()
    if not copies:
        return
    board_jobs = conn.execute(
        """SELECT j.id, j.title, j.status, j.notes FROM jobs j JOIN boards b ON b.id = j.board_id
           WHERE b.company_id = ? AND b.system != ? AND j.closed_at IS NULL ORDER BY j.id""",
        (company_id, SNAPSHOT_SYSTEM)).fetchall()
    for copy_id, title, status, notes, applied_at, changed_at in copies:
        match = next((job for job in board_jobs if same_job(title, job[1])), None)
        if match is None:
            conn.execute("UPDATE jobs SET closed_at = ? WHERE id = ?", (at, copy_id))
            done.closed += 1
            continue
        target, _, target_status, target_notes = match
        tracked = status != "new" or notes or applied_at
        if tracked:
            _move_tracking(conn, copy_id, target, status, notes, applied_at, changed_at, target_status, target_notes)
            done.tracking_moved += 1
        conn.execute("DELETE FROM jobs WHERE id = ?", (copy_id,))
        done.merged += 1
    # A snapshot board left with no jobs at all is just clutter on the company page.
    conn.execute(
        """DELETE FROM boards WHERE company_id = ? AND system = ?
           AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.board_id = boards.id)""",
        (company_id, SNAPSHOT_SYSTEM))


def _move_tracking(conn, copy_id, target, status, notes, applied_at, changed_at, target_status, target_notes) -> None:
    """The board job keeps its own status if you already set one there; notes are joined."""
    joined = "\n\n".join(n for n in (target_notes, notes) if n)
    if target_status == "new" and status != "new":
        conn.execute(
            "UPDATE jobs SET status = ?, status_changed_at = ?, notes = ?, "
            "applied_at = COALESCE(applied_at, ?) WHERE id = ?",
            (status, changed_at, joined, applied_at, target))
    else:
        conn.execute("UPDATE jobs SET notes = ?, applied_at = COALESCE(applied_at, ?) WHERE id = ?",
                     (joined, applied_at, target))
    conn.execute("UPDATE job_events SET job_id = ? WHERE job_id = ?", (target, copy_id))
