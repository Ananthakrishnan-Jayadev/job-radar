"""Only jobs posted in the last month are kept: scans skip older ones, old ones are
deleted after a scan (never tracked ones), and undated ones found long ago are hidden."""

from datetime import date

from jobradar import db, queries, scan, tracking
from jobradar.connectors import CONNECTORS, FetchResult
from jobradar.connectors._common import relative_date
from jobradar.models import Location, RawJob

TODAY = date(2026, 11, 18)
TORONTO = [Location("Toronto", "ON", "CA")]


def _raw(ext, title, posted):
    return RawJob(ext, title, f"https://x/{ext}", TORONTO, posted_at=posted)


def _board(conn):
    company = db.upsert_company(conn, "Acme", canadian=True)
    return db.upsert_board(conn, company, "ashby", "acme")


def _titles(conn):
    return sorted(r[0] for r in conn.execute("SELECT title FROM jobs"))


def test_scan_skips_and_deletes_old_postings_but_keeps_tracked(conn, settings, monkeypatch):
    settings.max_age_days = 30
    board = _board(conn)
    # Stored earlier: an old job you applied to, and an old one you didn't touch.
    applied = db.upsert_job(conn, board, _raw("1", "Applied Old", "2026-09-01"))[0]
    tracking.update_job(conn, applied, status="applied")
    db.upsert_job(conn, board, _raw("2", "Untouched Old", "2026-09-01"))

    listed = [_raw("1", "Applied Old", "2026-09-01"), _raw("2", "Untouched Old", "2026-09-01"),
              _raw("3", "Fresh", "2026-11-10"), _raw("4", "Brand New Old", "2026-10-01"),
              _raw("5", "No Date", None)]

    async def fake(board_, client, ctx):
        return FetchResult(jobs=listed, total=len(listed))

    monkeypatch.setitem(CONNECTORS, "ashby", fake)
    summary = scan.run_scan(conn, settings, today=TODAY)

    # Kept: what you track (even old), what's recent, what has no date.
    assert _titles(conn) == ["Applied Old", "Fresh", "No Date"]
    assert summary.pruned == 1  # "Untouched Old"; "Brand New Old" was never stored
    assert conn.execute("SELECT closed_at FROM jobs WHERE id = ?", (applied,)).fetchone()[0] is None


def test_no_age_limit_keeps_everything(conn, settings):
    settings.max_age_days = 0
    board = _board(conn)
    db.upsert_job(conn, board, _raw("1", "Ancient", "2020-01-01"))
    assert scan.prune_old(conn, settings, TODAY) == 0
    assert _titles(conn) == ["Ancient"]


def test_list_hides_undated_jobs_found_long_ago(conn):
    board = _board(conn)
    db.upsert_job(conn, board, _raw("1", "Undated Old", None), seen_at="2026-01-01T00:00:00+00:00")
    db.upsert_job(conn, board, _raw("2", "Undated New", None))
    saved = db.upsert_job(conn, board, _raw("3", "Undated Old Saved", None), seen_at="2026-01-01T00:00:00+00:00")[0]
    tracking.update_job(conn, saved, status="saved")

    def shown(**kw):
        return sorted(r["title"] for r in queries.search_jobs(conn, queries.JobFilter(all_roles=True, **kw))[1])

    assert shown(max_age_days=30) == ["Undated New", "Undated Old Saved"]
    assert shown(max_age_days=0) == ["Undated New", "Undated Old", "Undated Old Saved"]
    # Asking for jobs posted more than a month ago shows the old ones.
    assert "Undated Old" in shown(max_age_days=30, posted_before_days=30)


def test_workday_30_plus_days_is_old_not_undated():
    assert relative_date("Posted 30+ Days Ago", TODAY) == "2026-10-18"
    assert relative_date("Posted 3 Days Ago", TODAY) == "2026-11-15"
