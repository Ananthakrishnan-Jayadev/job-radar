"""Scan job boards and store what they list.

Each board is fetched and stored on its own: one broken source is recorded in
scan_results and the others carry on. Jobs missing from a complete, successful
read of their board are marked closed; a failed or partial read closes nothing.
A complete read also settles the company's Adzuna snapshot copies (snapshots.py).
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from . import db
from .config import Settings
from .connectors import CONNECTORS, FetchContext
from .http import HttpClient
from .locations import is_canadian
from .models import Board
from .roles import rules_for, sync_roles
from .snapshots import Retired, retire_copies

BOARDS_AT_ONCE = 6  # different hosts in parallel; each host is still limited by http.max_per_host


@dataclass
class BoardOutcome:
    board: Board
    ok: bool
    jobs_seen: int = 0  # all jobs the board listed
    jobs_canada: int = 0  # the ones stored
    jobs_new: int = 0
    jobs_closed: int = 0
    total_open: int | None = None
    complete: bool = False  # the whole board was read
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    ms: int = 0


@dataclass
class ScanSummary:
    scan_id: int
    outcomes: list[BoardOutcome]
    retired: Retired = field(default_factory=Retired)  # Adzuna snapshot copies settled

    @property
    def boards_ok(self) -> int:
        return sum(o.ok for o in self.outcomes)

    @property
    def boards_failed(self) -> int:
        return sum(not o.ok for o in self.outcomes)

    @property
    def jobs_new(self) -> int:
        return sum(o.jobs_new for o in self.outcomes)

    @property
    def jobs_closed(self) -> int:
        return sum(o.jobs_closed for o in self.outcomes)


def load_boards(conn: sqlite3.Connection, company: str | None = None) -> list[Board]:
    """Enabled boards that have a connector, optionally for one company (by name)."""
    sql = """
        SELECT b.*, c.name AS company_name, c.canadian AS company_canadian
        FROM boards b JOIN companies c ON c.id = b.company_id
        WHERE b.enabled = 1
    """
    params: list = []
    if company:
        sql += " AND c.name = ? COLLATE NOCASE"
        params.append(company)
    rows = conn.execute(sql + " ORDER BY c.name, b.system", params).fetchall()
    return [
        Board(id=r["id"], company_id=r["company_id"], company_name=r["company_name"],
              company_canadian=bool(r["company_canadian"]), system=r["system"],
              slug_or_url=r["slug_or_url"], confirmed=bool(r["confirmed"]), enabled=True)
        for r in rows if r["system"] in CONNECTORS
    ]


def source_terms(conn: sqlite3.Connection, settings: Settings) -> list[str]:
    """Plain search terms for sources that search on their own side.

    From saved searches marked for sources, else workday.search_terms in config.
    FTS syntax is flattened: '"machine learning" OR analy*' gives two terms.
    """
    rows = conn.execute("SELECT query FROM saved_searches WHERE use_for_sources = 1").fetchall()
    terms: list[str] = []
    for row in rows:
        for part in re.split(r"\s+OR\s+", row["query"]):
            term = re.sub(r'["*()]', " ", part)
            term = " ".join(w for w in term.split() if w not in ("AND", "NOT"))
            if term:
                terms.append(term)
    return list(dict.fromkeys(terms)) or list(settings.workday.search_terms)


def _known_ids(conn: sqlite3.Connection, board_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT external_id FROM jobs WHERE board_id = ? AND description IS NOT NULL", (board_id,)
    ).fetchall()
    return {r[0] for r in rows}


async def _scan_board(conn, board: Board, client: HttpClient, settings: Settings,
                      terms: list[str], seen_at: str, today) -> BoardOutcome:
    started = time.monotonic()
    rules = rules_for(settings.root)
    ctx = FetchContext(settings=settings, search_terms=terms, known_ids=_known_ids(conn, board.id), today=today,
                       wants=rules.wanted if rules else None)
    try:
        result = await CONNECTORS[board.system](board, client, ctx)
    except Exception as exc:  # noqa: BLE001 - any failure is this board's error, never the scan's
        message = str(exc) or type(exc).__name__
        return BoardOutcome(board=board, ok=False, error=message, ms=int((time.monotonic() - started) * 1000))

    outcome = BoardOutcome(board=board, ok=True, jobs_seen=len(result.jobs), total_open=result.total,
                           complete=result.complete, warnings=list(result.warnings))
    seen_ids: list[int] = []
    for job in result.jobs:
        if not is_canadian(job.locations, board.company_canadian):
            continue
        job_id, is_new = db.upsert_job(conn, board.id, job, seen_at)
        seen_ids.append(job_id)
        outcome.jobs_canada += 1
        outcome.jobs_new += is_new
    if result.complete:
        with conn:
            cur = conn.execute(
                "UPDATE jobs SET closed_at = ? WHERE board_id = ? AND closed_at IS NULL "
                "AND id NOT IN (SELECT value FROM json_each(?))",
                (seen_at, board.id, json.dumps(seen_ids)),
            )
        outcome.jobs_closed = cur.rowcount
    outcome.ms = int((time.monotonic() - started) * 1000)
    return outcome


def _record(conn: sqlite3.Connection, scan_id: int, outcome: BoardOutcome, seen_at: str) -> None:
    with conn:
        if outcome.ok:
            conn.execute(
                "UPDATE boards SET last_scanned_at = ?, last_error = NULL, total_open = ? WHERE id = ?",
                (seen_at, outcome.total_open, outcome.board.id),
            )
        else:
            conn.execute(
                "UPDATE boards SET last_scanned_at = ?, last_error = ? WHERE id = ?",
                (seen_at, outcome.error, outcome.board.id),
            )
        conn.execute(
            "INSERT INTO scan_results (scan_id, board_id, ok, jobs_seen, jobs_canada, error, ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (scan_id, outcome.board.id, int(outcome.ok), outcome.jobs_seen, outcome.jobs_canada,
             outcome.error or ("; ".join(outcome.warnings) or None), outcome.ms),
        )


async def scan_async(
    conn: sqlite3.Connection,
    settings: Settings,
    *,
    company: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    progress: Callable[[BoardOutcome], None] | None = None,
    today=None,
) -> ScanSummary:
    boards = load_boards(conn, company)
    seen_at = db.now()
    with conn:
        scan_id = conn.execute("INSERT INTO scans (started_at) VALUES (?)", (seen_at,)).lastrowid
    terms = source_terms(conn, settings)
    limit = asyncio.Semaphore(BOARDS_AT_ONCE)
    outcomes: list[BoardOutcome] = []

    async with HttpClient(settings, transport=transport) as client:
        async def run(board: Board) -> None:
            async with limit:
                outcome = await _scan_board(conn, board, client, settings, terms, seen_at, today)
            _record(conn, scan_id, outcome, seen_at)
            outcomes.append(outcome)
            if progress:
                progress(outcome)

        await asyncio.gather(*(run(b) for b in boards))

    read_fully = [o.board.id for o in outcomes if o.ok and o.complete]
    summary = ScanSummary(scan_id=scan_id, outcomes=outcomes, retired=retire_copies(conn, read_fully, seen_at))
    sync_roles(conn, settings.root)  # role categories for the new jobs
    with conn:
        conn.execute(
            "UPDATE scans SET finished_at = ?, boards_ok = ?, boards_failed = ?, jobs_new = ?, jobs_closed = ? "
            "WHERE id = ?",
            (db.now(), summary.boards_ok, summary.boards_failed, summary.jobs_new, summary.jobs_closed, scan_id),
        )
    return summary


def run_scan(conn: sqlite3.Connection, settings: Settings, **kwargs) -> ScanSummary:
    """Blocking wrapper around scan_async, for the command line."""
    return asyncio.run(scan_async(conn, settings, **kwargs))
