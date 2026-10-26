"""Runs one scan at a time in a background thread for the "Scan now" button.

The thread opens its own SQLite connection (connections can't be shared
across threads); the API reads progress from `state()`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .. import db
from ..config import Settings
from ..scan import BoardOutcome, load_boards, run_scan


@dataclass
class ScanState:
    running: bool = False
    company: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    boards_total: int = 0
    boards_done: int = 0
    boards_failed: int = 0
    jobs_new: int = 0
    jobs_closed: int = 0
    scan_id: int | None = None
    error: str | None = None  # the scan itself crashed (not one board)
    recent: list[dict] = field(default_factory=list)  # last finished boards, newest first


class ScanRunner:
    def __init__(self, settings: Settings, db_path: Path, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.db_path = db_path
        self.transport = transport
        self._lock = threading.Lock()
        self._state = ScanState()
        self._thread: threading.Thread | None = None

    def state(self) -> dict:
        with self._lock:
            return {**self._state.__dict__, "recent": list(self._state.recent)}

    def start(self, company: str | None = None) -> bool:
        """Start a scan. False if one is already running."""
        with self._lock:
            if self._state.running:
                return False
            conn = db.connect(self.db_path)
            try:
                total = len(load_boards(conn, company))
            finally:
                conn.close()
            self._state = ScanState(running=True, company=company, started_at=db.now(), boards_total=total)
            self._thread = threading.Thread(target=self._run, args=(company,), daemon=True, name="jobradar-scan")
            self._thread.start()
        return True

    def wait(self, timeout: float | None = None) -> None:
        """Block until the current scan finishes (used by tests)."""
        if self._thread:
            self._thread.join(timeout)

    def _progress(self, outcome: BoardOutcome) -> None:
        with self._lock:
            s = self._state
            s.boards_done += 1
            s.boards_failed += not outcome.ok
            s.jobs_new += outcome.jobs_new
            s.jobs_closed += outcome.jobs_closed
            s.recent.insert(0, {
                "company": outcome.board.company_name, "system": outcome.board.system, "ok": outcome.ok,
                "jobs_canada": outcome.jobs_canada, "jobs_new": outcome.jobs_new, "error": outcome.error,
            })
            del s.recent[10:]

    def _run(self, company: str | None) -> None:
        conn = db.connect(self.db_path)
        try:
            summary = run_scan(conn, self.settings, company=company, transport=self.transport,
                               progress=self._progress)
            with self._lock:
                self._state.scan_id = summary.scan_id
        except Exception as exc:  # noqa: BLE001 - shown in the UI instead of killing the thread silently
            with self._lock:
                self._state.error = str(exc) or type(exc).__name__
        finally:
            conn.close()
            with self._lock:
                self._state.running = False
                self._state.finished_at = db.now()
