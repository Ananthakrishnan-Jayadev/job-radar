"""One long-running chore at a time (filling sizes, finding boards) in a thread.

Like the scan runner, the work opens its own database connection; the API
reads progress from `state()`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from .. import db

# work(progress) -> a one-line result; progress(done, total)
Work = Callable[[Callable[[int, int], None]], str]


@dataclass
class TaskState:
    name: str | None = None
    running: bool = False
    done: int = 0
    total: int = 0
    result: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class TaskRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = TaskState()
        self._thread: threading.Thread | None = None

    def state(self) -> dict:
        with self._lock:
            return dict(self._state.__dict__)

    def start(self, name: str, work: Work) -> bool:
        with self._lock:
            if self._state.running:
                return False
            self._state = TaskState(name=name, running=True, started_at=db.now())
            self._thread = threading.Thread(target=self._run, args=(work,), daemon=True, name=f"jobradar-{name}")
            self._thread.start()
        return True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _progress(self, done: int, total: int) -> None:
        with self._lock:
            self._state.done, self._state.total = done, total

    def _run(self, work: Work) -> None:
        try:
            result = work(self._progress)
            with self._lock:
                self._state.result = result
        except Exception as exc:  # noqa: BLE001 - reported in the UI
            with self._lock:
                self._state.error = str(exc) or type(exc).__name__
        finally:
            with self._lock:
                self._state.running = False
                self._state.finished_at = db.now()
