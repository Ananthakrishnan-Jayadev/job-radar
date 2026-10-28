"""The Applications page: counts, the weekly chart, follow-ups, saved jobs."""

from datetime import date

from fastapi.testclient import TestClient

from jobradar import db, tracking
from jobradar.dashboard import application_dashboard
from jobradar.models import Location, RawJob
from jobradar.web import app as web_app

TODAY = date(2026, 10, 28)  # a Wednesday


def _jobs(conn, n=6):
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "ashby", "acme")
    return [db.upsert_job(conn, board, RawJob(str(i), f"Job {i}", f"u{i}", [Location("Toronto", "ON", "CA")]))[0]
            for i in range(n)]


def _set(conn, job_id, status, changed, applied=None):
    tracking.update_job(conn, job_id, status=status)
    with conn:
        conn.execute("UPDATE jobs SET status_changed_at = ?, applied_at = COALESCE(?, applied_at) WHERE id = ?",
                     (changed, applied, job_id))


def test_empty(conn):
    _jobs(conn)
    d = application_dashboard(conn, TODAY)
    assert d["counts"] == {"saved": 0, "applied": 0, "interviewing": 0, "offer": 0, "rejected": 0,
                           "not_interested": 0}
    assert (d["applied_total"], d["heard_back"], d["interviews"]) == (0, 0, 0)
    assert len(d["per_week"]) == 12 and d["per_week"][-1] == {"week": "2026-10-26", "applied": 0}
    assert d["follow_up"] == d["active"] == d["saved"] == d["recent"] == []


def test_counts_and_follow_ups(conn):
    a, b, c, d_, e, f = _jobs(conn)
    _set(conn, a, "saved", "2026-10-27T10:00:00+00:00")
    _set(conn, b, "applied", "2026-10-01T10:00:00+00:00", "2026-10-01")  # 27 days: follow up
    _set(conn, c, "applied", "2026-10-25T10:00:00+00:00", "2026-10-25")  # 3 days: wait
    _set(conn, d_, "applied", "2026-10-10T10:00:00+00:00", "2026-10-06")
    _set(conn, d_, "interviewing", "2026-10-12T10:00:00+00:00")
    _set(conn, e, "applied", "2026-10-20T10:00:00+00:00", "2026-10-20")
    _set(conn, e, "rejected", "2026-10-22T10:00:00+00:00")
    _set(conn, f, "not_interested", "2026-10-22T10:00:00+00:00")
    d = application_dashboard(conn, TODAY)
    assert d["counts"]["applied"] == 2 and d["counts"]["interviewing"] == 1 and d["counts"]["rejected"] == 1
    assert (d["applied_total"], d["heard_back"], d["interviews"]) == (4, 2, 1)
    assert [r["id"] for r in d["follow_up"]] == [b, d_]  # longest without news first; c is recent
    assert next(r for r in d["follow_up"] if r["id"] == b)["days_since_change"] == 27
    assert {r["id"] for r in d["active"]} == {b, c, d_}
    assert [r["id"] for r in d["saved"]] == [a]
    weeks = {w["week"]: w["applied"] for w in d["per_week"]}
    assert (weeks["2026-09-28"], weeks["2026-10-05"], weeks["2026-10-19"]) == (1, 1, 2)  # Mondays
    assert d["recent"][0]["new"] == "not_interested" and d["recent"][0]["title"] == "Job 5"


def test_heard_back_counts_a_past_interview(conn):
    (a, *_) = _jobs(conn, 1)
    _set(conn, a, "applied", "2026-10-01T10:00:00+00:00", "2026-10-01")
    _set(conn, a, "interviewing", "2026-10-05T10:00:00+00:00")
    _set(conn, a, "not_interested", "2026-10-07T10:00:00+00:00")  # you withdrew
    d = application_dashboard(conn, TODAY)
    assert (d["applied_total"], d["heard_back"], d["interviews"]) == (1, 1, 1)


def test_saved_job_whose_posting_closed(conn):
    a, b = _jobs(conn, 2)
    _set(conn, a, "saved", "2026-10-27T10:00:00+00:00")
    _set(conn, b, "saved", "2026-10-26T10:00:00+00:00")
    with conn:
        conn.execute("UPDATE jobs SET closed_at = '2026-10-27T12:00:00+00:00' WHERE id = ?", (a,))
    saved = application_dashboard(conn, TODAY)["saved"]
    assert [r["id"] for r in saved] == [b, a]  # still open first
    assert saved[1]["closed_at"]


def test_api(conn, tmp_path, settings):
    (a, *_) = _jobs(conn, 1)
    tracking.update_job(conn, a, status="applied")
    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db"))
    d = client.get("/api/applications").json()
    assert d["counts"]["applied"] == 1 and d["applied_total"] == 1
    assert d["active"][0]["company"] == "Acme" and d["active"][0]["days_since_change"] == 0
