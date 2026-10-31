"""The Applications page: where each tracked job stands, and how the search is going.

Covers every job you've given a status, wherever it is and whatever its role:
tracking always counts, even after the posting disappears.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from .models import JOB_STATUSES

FOLLOW_UP_DAYS = 14  # no news for this long on an application: time to follow up
WEEKS = 12  # applications-per-week chart
APPLIED_OR_LATER = ("applied", "interviewing", "offer", "rejected")
WAITING = ("applied", "interviewing")  # still waiting on the company
RECENT_EVENTS = 15

_ROW = """
    SELECT j.id, j.title, j.url, j.status, j.applied_at, j.status_changed_at, j.closed_at, j.first_seen,
           j.experience_level AS level, c.id AS company_id, c.name AS company
    FROM jobs j JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id
"""


def _day(text: str | None) -> date | None:
    """Your local day for a stored time (UTC), or a date as it is: an evening
    change counts as today, not tomorrow."""
    if not text:
        return None
    if len(text) <= 10:
        return date.fromisoformat(text)
    moment = datetime.fromisoformat(text)
    return (moment.astimezone() if moment.tzinfo else moment).date()


def _row(r: sqlite3.Row, today: date) -> dict:
    row = dict(r)
    last = _day(row["status_changed_at"]) or _day(row["applied_at"])
    row["days_since_change"] = (today - last).days if last else None
    row["days_since_applied"] = (today - _day(row["applied_at"])).days if row["applied_at"] else None
    return row


def application_dashboard(conn: sqlite3.Connection, today: date | None = None) -> dict:
    today = today or datetime.now().date()
    counts = dict.fromkeys(JOB_STATUSES[1:], 0)
    counts.update(dict(conn.execute(
        "SELECT status, COUNT(*) FROM jobs WHERE status != 'new' GROUP BY status").fetchall()))

    marks = ", ".join("?" * len(APPLIED_OR_LATER))
    applied = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE applied_at IS NOT NULL OR status IN ({marks})", APPLIED_OR_LATER
    ).fetchone()[0]
    # Heard back: the company answered (an interview, an offer or a no), now or at any point.
    heard_back = conn.execute(f"""
        SELECT COUNT(*) FROM jobs j
        WHERE (j.applied_at IS NOT NULL OR j.status IN ({marks}))
          AND (j.status IN ('interviewing', 'offer', 'rejected')
               OR EXISTS (SELECT 1 FROM job_events e WHERE e.job_id = j.id AND e.field = 'status'
                          AND e.new IN ('interviewing', 'offer', 'rejected')))
    """, APPLIED_OR_LATER).fetchone()[0]
    interviews = conn.execute("""
        SELECT COUNT(*) FROM jobs j
        WHERE j.status IN ('interviewing', 'offer')
           OR EXISTS (SELECT 1 FROM job_events e WHERE e.job_id = j.id AND e.field = 'status'
                      AND e.new IN ('interviewing', 'offer'))
    """).fetchone()[0]

    # Weeks start on Monday; the last one is the current week.
    this_week = today - timedelta(days=today.weekday())
    starts = [this_week - timedelta(weeks=n) for n in range(WEEKS - 1, -1, -1)]
    per_week = dict.fromkeys(starts, 0)
    for (day,) in conn.execute("SELECT applied_at FROM jobs WHERE applied_at >= ?", (starts[0].isoformat(),)):
        d = _day(day)
        week = d - timedelta(days=d.weekday())
        if week in per_week:
            per_week[week] += 1

    def rows(where: str, params=(), order: str = "j.status_changed_at DESC") -> list[dict]:
        return [_row(r, today) for r in conn.execute(f"{_ROW} WHERE {where} ORDER BY {order}", params)]

    waiting = rows(f"j.status IN ({', '.join('?' * len(WAITING))})", WAITING,
                   order="COALESCE(j.status_changed_at, j.applied_at)")
    events = [dict(r) for r in conn.execute(f"""
        SELECT e.at, e.old, e.new, j.id, j.title, c.id AS company_id, c.name AS company
        FROM job_events e JOIN jobs j ON j.id = e.job_id
        JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id
        WHERE e.field = 'status' ORDER BY e.id DESC LIMIT {RECENT_EVENTS}
    """)]
    return {
        "today": today.isoformat(),
        "counts": counts,
        "applied_total": applied,
        "heard_back": heard_back,
        "interviews": interviews,
        "follow_up_days": FOLLOW_UP_DAYS,
        "per_week": [{"week": w.isoformat(), "applied": n} for w, n in per_week.items()],
        "follow_up": [r for r in waiting if (r["days_since_change"] or 0) >= FOLLOW_UP_DAYS],
        "active": rows("j.status IN ('applied', 'interviewing', 'offer')"),
        "saved": rows("j.status = 'saved'", order="j.closed_at IS NOT NULL, j.status_changed_at DESC"),
        "recent": events,
    }
