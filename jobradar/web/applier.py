"""One application window at a time, in a thread; the API reads its state.

Phases: opening → filling → ready (waiting for you) → submitted / closed, or
error. Like the scan runner, the work opens its own database connection.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from .. import db
from ..apply.greenhouse import Plan
from ..apply.run import apply_job

FINISHED = ("submitted", "closed", "error")


class ApplyRunner:
    def __init__(self, db_path: Path, filler=None):
        self.db_path = db_path
        self.filler = filler  # tests swap the browser out
        self._lock = threading.Lock()
        self._state: dict = {"phase": None}
        self._thread: threading.Thread | None = None

    def state(self) -> dict:
        with self._lock:
            return dict(self._state)

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._state.get("phase") not in (None, *FINISHED)

    def start(self, plan: Plan, resume_name: str) -> bool:
        with self._lock:
            if self._state.get("phase") not in (None, *FINISHED):
                return False
            self._state = {"phase": "opening", "job_id": plan.job_id, "title": plan.title, "company": plan.company,
                           "resume": resume_name, "filled": [], "todo": [], "message": "Opening a browser window…",
                           "started_at": db.now()}
            self._thread = threading.Thread(target=self._run, args=(plan, resume_name), daemon=True,
                                            name="jobradar-apply")
            self._thread.start()
        return True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _report(self, change: dict) -> None:
        with self._lock:
            self._state.update(change)

    def _run(self, plan: Plan, resume_name: str) -> None:
        try:
            kwargs: dict[str, Callable] = {"filler": self.filler} if self.filler else {}
            outcome = apply_job(self.db_path, plan, resume_name, self._report, **kwargs)
            self._report({"phase": outcome, "message": (
                "Submitted: the job is marked Applied." if outcome == "submitted"
                else "The window was closed without submitting; nothing changed.")})
        except Exception as exc:  # noqa: BLE001 - shown in the UI
            self._report({"phase": "error", "message": str(exc) or type(exc).__name__})
        finally:
            self._report({"finished_at": db.now()})
