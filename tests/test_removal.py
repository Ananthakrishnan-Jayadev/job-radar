"""Removing companies: archived first, tracked ones kept unless asked, and the web endpoint."""

import sqlite3

from fastapi.testclient import TestClient

from jobradar import db, removal, tracking
from jobradar.models import Location, RawJob
from jobradar.web import app as web_app


def _company(conn, name, jobs=1):
    company = db.upsert_company(conn, name, canadian=True)
    board = db.upsert_board(conn, company, "ashby", name.lower())
    ids = [db.upsert_job(conn, board, RawJob(str(i), f"{name} Analyst {i}", f"u{name}{i}",
                                             [Location("Toronto", "ON", "CA")]))[0] for i in range(jobs)]
    return company, ids


def test_remove_archives_then_deletes(conn, tmp_path):
    acme, acme_jobs = _company(conn, "Acme", jobs=2)
    keep, _ = _company(conn, "Keep")
    result = removal.remove_companies(conn, [acme], tmp_path / "data")

    assert result["removed"] == [{"id": acme, "name": "Acme"}]
    assert (result["kept"], result["jobs"]) == ([], 2)
    names = [r["name"] for r in conn.execute("SELECT name FROM companies")]
    assert names == ["Keep"]
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    # Search no longer finds the removed jobs.
    assert db.search_jobs(conn, "Acme") == []

    archive = tmp_path / "data" / result["archive"]
    assert archive.name.startswith("removed-companies-")
    copy = db.connect(archive)
    assert [r["name"] for r in copy.execute("SELECT name FROM companies")] == ["Acme"]
    assert copy.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    assert copy.execute("SELECT COUNT(*) FROM job_locations").fetchone()[0] == 2
    assert copy.execute("PRAGMA foreign_key_check").fetchall() == []
    copy.close()
    assert keep in [r["id"] for r in conn.execute("SELECT id FROM companies")]


def test_tracked_companies_are_kept_unless_asked(conn, tmp_path):
    applied, (job,) = _company(conn, "Applied Co")
    plain, _ = _company(conn, "Plain Co")
    tracking.update_job(conn, job, status="applied")

    result = removal.remove_companies(conn, [applied, plain], tmp_path)
    assert result["removed"] == [{"id": plain, "name": "Plain Co"}]
    assert result["kept"] == [{"id": applied, "name": "Applied Co", "tracked": 1}]

    result = removal.remove_companies(conn, [applied], tmp_path, include_tracked=True)
    assert result["removed"] == [{"id": applied, "name": "Applied Co"}]
    archive = sqlite3.connect(tmp_path / result["archive"])
    # The tracking travels with it, history included.
    assert archive.execute("SELECT status FROM jobs").fetchone()[0] == "applied"
    assert archive.execute("SELECT COUNT(*) FROM job_events").fetchone()[0] >= 1
    archive.close()


def test_nothing_to_remove(conn, tmp_path):
    result = removal.remove_companies(conn, [999], tmp_path)
    assert result == {"removed": [], "kept": [], "jobs": 0, "archive": None}
    assert list(tmp_path.glob("removed-companies-*")) == []


def test_remove_endpoint(settings, tmp_path):
    db_path = tmp_path / "web.db"
    conn = db.connect(db_path)
    a, _ = _company(conn, "Alpha")
    b, (job,) = _company(conn, "Beta")
    tracking.update_job(conn, job, status="saved")
    conn.close()
    client = TestClient(web_app.create_app(settings, db_path))

    assert client.post("/api/companies/remove", json={"ids": []}).status_code == 422
    body = client.post("/api/companies/remove", json={"ids": [a, b]}).json()
    assert [c["name"] for c in body["removed"]] == ["Alpha"]
    assert [c["name"] for c in body["kept"]] == ["Beta"]
    assert [c["name"] for c in client.get("/api/companies").json()] == ["Beta"]

    body = client.post("/api/companies/remove", json={"ids": [b], "include_tracked": True}).json()
    assert [c["name"] for c in body["removed"]] == ["Beta"]
    assert client.get("/api/companies").json() == []
