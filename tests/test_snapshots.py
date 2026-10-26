"""Adzuna snapshot copies retired once the company's own board is read."""

import pytest

from jobradar import db, tracking
from jobradar.models import Location, RawJob
from jobradar.scan import run_scan
from jobradar.snapshots import retire_copies, same_job

from conftest import FakeSources

GH = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
TORONTO = [Location("Toronto", "ON", "CA")]


@pytest.mark.parametrize("snapshot, board", [
    ("Senior Data Engineer", "Senior Data Engineer"),
    ("Software Engineer, AI Vancouver, BC", "Software Engineer, AI"),
    ("Software Engineer, Data Systems (Python) New Remote - Canada", "Software Engineer, Data Systems (Python)"),
    ("Senior Applied Scientist CA$123K – CA$205K • Offers Equity • Offers Bonus", "Senior Applied Scientist"),
    ("Sr. Data Scientist, Algorithms Vancouver, British Columbia, Canada", "Sr. Data Scientist, Algorithms"),
])
def test_same_job(snapshot, board):
    assert same_job(snapshot, board)


@pytest.mark.parametrize("snapshot, board", [
    ("Senior Software Engineer, Data Infrastructure", "Senior Software Engineer"),
    ("Senior Data Engineer", "Senior DevOps Engineer"),
    ("Engineering Senior Applied Scientist", "Senior Applied Scientist"),
    ("Data Engineer", ""),
])
def test_not_same_job(snapshot, board):
    assert not same_job(snapshot, board)


def setup(conn, confirmed=True):
    company = db.upsert_company(conn, "Acme", canadian=True)
    real = db.upsert_board(conn, company, "greenhouse", "acme", confirmed=confirmed)
    snap = db.upsert_board(conn, company, "adzuna", "acme-snapshot")
    ids = {}
    for ext, title in (("a1", "Data Engineer Toronto, ON"), ("a2", "ML Engineer"), ("a3", "Data Analyst")):
        ids[ext], _ = db.upsert_job(conn, snap, RawJob(ext, title, f"https://adzuna/{ext}", TORONTO,
                                                       description="snippet…"))
    conn.commit()
    return real, snap, ids


def gh_page(*titles):
    return {"jobs": [{"id": i, "title": t, "absolute_url": f"https://x/{i}", "location": {"name": "Toronto, ON"},
                      "content": "&lt;p&gt;Full description&lt;/p&gt;"} for i, t in enumerate(titles)],
            "meta": {"total": len(titles)}}


def test_scan_merges_matches_and_closes_the_rest(conn, settings):
    _, _, ids = setup(conn)
    tracking.update_job(conn, ids["a1"], status="applied", notes="sent CV", applied_at="2026-10-20")
    summary = run_scan(conn, settings, transport=FakeSources({("GET", GH): gh_page("Data Engineer", "Barista")}).transport())
    assert (summary.retired.merged, summary.retired.closed, summary.retired.tracking_moved) == (1, 2, 1)

    rows = conn.execute("""SELECT j.title, b.system, j.closed_at IS NULL, j.status, j.notes, j.applied_at
                           FROM jobs j JOIN boards b ON b.id = j.board_id ORDER BY j.id""").fetchall()
    by_title = {r[0]: r[1:] for r in rows}
    assert "Data Engineer Toronto, ON" not in by_title  # the copy is gone
    assert by_title["Data Engineer"] == ("greenhouse", 1, "applied", "sent CV", "2026-10-20")
    assert by_title["ML Engineer"][:2] == ("adzuna", 0)  # not on the board any more: closed
    real_id = conn.execute("SELECT id FROM jobs WHERE title = 'Data Engineer'").fetchone()[0]
    assert [e["new"] for e in tracking.job_events(conn, real_id)] == ["applied"]


def test_snapshot_board_removed_once_empty(conn, settings):
    setup(conn)
    sources = FakeSources({("GET", GH): gh_page("Data Engineer", "ML Engineer", "Data Analyst")})
    summary = run_scan(conn, settings, transport=sources.transport())
    assert summary.retired.merged == 3
    assert conn.execute("SELECT COUNT(*) FROM boards WHERE system = 'adzuna'").fetchone()[0] == 0


def test_failed_or_unconfirmed_board_leaves_copies_alone(conn, settings):
    real, _, _ = setup(conn, confirmed=False)
    summary = run_scan(conn, settings, transport=FakeSources({("GET", GH): gh_page("Data Engineer")}).transport())
    assert summary.retired.closed == 0
    conn.execute("UPDATE boards SET confirmed = 1 WHERE id = ?", (real,))
    conn.commit()
    summary = run_scan(conn, settings, transport=FakeSources({("GET", GH): Exception("down")}).transport())
    assert (summary.retired.merged, summary.retired.closed) == (0, 0)
    open_copies = conn.execute("SELECT COUNT(*) FROM jobs j JOIN boards b ON b.id = j.board_id "
                               "WHERE b.system = 'adzuna' AND j.closed_at IS NULL").fetchone()[0]
    assert open_copies == 3


def test_board_job_keeps_its_own_status(conn):
    real, _, ids = setup(conn)
    board_job, _ = db.upsert_job(conn, real, RawJob("1", "ML Engineer", "u", TORONTO))
    conn.commit()
    tracking.update_job(conn, board_job, status="saved", notes="looks good")
    tracking.update_job(conn, ids["a2"], status="not_interested", notes="too senior")
    retire_copies(conn, [real], db.now())
    status, notes = conn.execute("SELECT status, notes FROM jobs WHERE id = ?", (board_job,)).fetchone()
    assert (status, notes) == ("saved", "looks good\n\ntoo senior")
