"""One application from start to end: plan the answers, fill the form, wait
for you, then mark the job Applied if you submitted it."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx

from .. import db, resumes, tracking
from ..config import Settings
from ..http import FetchError, HttpClient
from ..profile import load_profile
from .browser import fill_and_watch
from .greenhouse import ApplyError, Plan, prepare


def plan_application(conn, settings: Settings, job_id: int, resume_name: str, data_dir: Path,
                     transport: httpx.AsyncBaseTransport | None = None) -> Plan:
    """Everything that can go wrong before a window opens, checked up front.
    *data_dir* holds the database, and the résumés in its resumes/ folder."""
    profile = load_profile(settings.root)
    resume = resumes.resume_path(data_dir, resume_name)

    async def go():
        async with HttpClient(settings, transport=transport) as client:
            return await prepare(conn, client, job_id, profile, resume)
    try:
        return asyncio.run(go())
    except FetchError as exc:
        raise ApplyError(f"Couldn't read the job's application questions from Greenhouse: {exc}") from exc


def record_submitted(conn, job_id: int, resume_name: str) -> None:
    """Applied, today, with a note of the résumé used (your notes are kept above it)."""
    row = conn.execute("SELECT status, notes FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row["status"] in ("new", "saved"):
        tracking.update_job(conn, job_id, status="applied")
    line = f"Applied through Job Radar on {db.now()[:10]} with {resume_name}."
    tracking.update_job(conn, job_id, notes=f"{row['notes']}\n{line}".strip())


def apply_job(db_path: Path, plan: Plan, resume_name: str, report: Callable[[dict], None],
              filler=fill_and_watch) -> str:
    """Fill in and watch; afterwards record the outcome. Returns "submitted" or "closed"."""
    outcome = filler(plan, report)
    if outcome == "submitted":
        conn = db.connect(db_path)
        try:
            record_submitted(conn, plan.job_id, resume_name)
        finally:
            conn.close()
    return outcome
