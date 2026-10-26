import httpx
import pytest

from jobradar import db
from jobradar.scan import load_boards, run_scan, source_terms

from conftest import FakeSources, fixture_json

GH = "https://boards-api.greenhouse.io/v1/boards/"


def gh_job(i, place="Toronto, ON", title=None):
    return {"id": i, "title": title or f"Job {i}", "absolute_url": f"https://x/{i}", "location": {"name": place}}


def gh(*jobs, total=None):
    return {"jobs": list(jobs), "meta": {"total": total or len(jobs)}}


@pytest.fixture
def acme(conn):
    company_id = db.upsert_company(conn, "Acme", canadian=True)
    return db.upsert_board(conn, company_id, "greenhouse", "acme")


def scan(conn, settings, sources, **kw):
    return run_scan(conn, settings, transport=sources.transport(), **kw)


def open_titles(conn):
    return sorted(r[0] for r in conn.execute("SELECT title FROM jobs WHERE closed_at IS NULL"))


def test_stores_only_canadian_jobs_but_counts_all(conn, settings, acme):
    sources = FakeSources({("GET", GH + "acme"): gh(gh_job(1), gh_job(2, "New York, NY"), gh_job(3, "Remote"))})
    summary = scan(conn, settings, sources)
    outcome = summary.outcomes[0]
    assert (outcome.ok, outcome.jobs_seen, outcome.jobs_canada, outcome.jobs_new) == (True, 3, 2, 2)
    # "Remote" with no country counts as Canadian because Acme is Canadian.
    assert open_titles(conn) == ["Job 1", "Job 3"]
    board = conn.execute("SELECT * FROM boards WHERE id = ?", (acme,)).fetchone()
    assert board["total_open"] == 3
    assert board["last_error"] is None and board["last_scanned_at"]


def test_remote_without_country_skipped_for_foreign_company(conn, settings):
    company_id = db.upsert_company(conn, "Globex", canadian=False)
    db.upsert_board(conn, company_id, "greenhouse", "globex")
    sources = FakeSources({("GET", GH + "globex"): gh(gh_job(1, "Remote"), gh_job(2, "Remote - Canada"))})
    scan(conn, settings, sources)
    assert open_titles(conn) == ["Job 2"]


def test_lifecycle_new_closed_reopened(conn, settings, acme):
    route = ("GET", GH + "acme")
    sources = FakeSources({route: gh(gh_job(1), gh_job(2))})
    first = scan(conn, settings, sources)
    assert (first.jobs_new, first.jobs_closed) == (2, 0)

    conn.execute("UPDATE jobs SET status = 'applied', notes = 'sent' WHERE external_id = '2'")
    sources.routes[route] = gh(gh_job(1))
    second = scan(conn, settings, sources)
    assert (second.jobs_new, second.jobs_closed) == (0, 1)
    closed = conn.execute("SELECT * FROM jobs WHERE external_id = '2'").fetchone()
    assert closed["closed_at"] is not None
    assert (closed["status"], closed["notes"]) == ("applied", "sent")  # tracking survives closing

    sources.routes[route] = gh(gh_job(1), gh_job(2))
    third = scan(conn, settings, sources)
    assert (third.jobs_new, third.jobs_closed) == (0, 0)
    assert open_titles(conn) == ["Job 1", "Job 2"]


def test_failed_scan_closes_nothing_and_records_error(conn, settings, acme):
    route = ("GET", GH + "acme")
    sources = FakeSources({route: gh(gh_job(1))})
    scan(conn, settings, sources)

    sources.routes[route] = httpx.Response(500)
    summary = scan(conn, settings, sources)
    assert summary.boards_failed == 1
    assert summary.outcomes[0].error == "HTTP 500"
    assert open_titles(conn) == ["Job 1"]
    assert conn.execute("SELECT last_error FROM boards").fetchone()[0] == "HTTP 500"

    sources.routes[route] = gh(gh_job(1))
    scan(conn, settings, sources)
    assert conn.execute("SELECT last_error FROM boards").fetchone()[0] is None


def test_partial_read_closes_nothing(conn, settings):
    company_id = db.upsert_company(conn, "nesto", canadian=True)
    db.upsert_board(conn, company_id, "rippling", "nesto")
    page = fixture_json("rippling_nesto.json")
    page["totalPages"], page["totalItems"] = 1, 2
    sources = FakeSources({("GET", "https://ats.rippling.com/"): page})
    scan(conn, settings, sources)
    assert len(open_titles(conn)) == 2

    # Now the board claims two pages but repeats the first: a partial read.
    page = fixture_json("rippling_nesto.json")
    page["items"] = page["items"][:1]
    sources.routes[("GET", "https://ats.rippling.com/")] = page
    summary = scan(conn, settings, sources)
    assert summary.jobs_closed == 0
    assert len(open_titles(conn)) == 2


def test_one_broken_board_does_not_stop_others(conn, settings, acme):
    other = db.upsert_company(conn, "Broken", canadian=True)
    db.upsert_board(conn, other, "lever", "broken")  # no route: 404
    sources = FakeSources({("GET", GH + "acme"): gh(gh_job(1))})
    summary = scan(conn, settings, sources)
    assert (summary.boards_ok, summary.boards_failed) == (1, 1)
    failed = next(o for o in summary.outcomes if not o.ok)
    assert "404" in failed.error
    scans = conn.execute("SELECT * FROM scans").fetchone()
    assert (scans["boards_ok"], scans["boards_failed"], scans["jobs_new"]) == (1, 1, 1)
    assert scans["finished_at"]
    assert conn.execute("SELECT COUNT(*) FROM scan_results").fetchone()[0] == 2


def test_scan_one_company_and_skip_disabled(conn, settings, acme):
    other = db.upsert_company(conn, "Other", canadian=True)
    db.upsert_board(conn, other, "greenhouse", "other")
    db.upsert_board(conn, other, "lever", "other-old", enabled=False)
    assert [b.slug_or_url for b in load_boards(conn, "other")] == ["other"]
    sources = FakeSources({("GET", GH): gh(gh_job(1))})
    summary = scan(conn, settings, sources, company="ACME")
    assert [o.board.company_name for o in summary.outcomes] == ["Acme"]


def test_progress_callback(conn, settings, acme):
    seen = []
    sources = FakeSources({("GET", GH + "acme"): gh(gh_job(1))})
    scan(conn, settings, sources, progress=seen.append)
    assert [o.board.slug_or_url for o in seen] == ["acme"]


def test_workday_partial_details_keep_stored_locations(conn, settings):
    """A later list-only read must not wipe locations taken from the detail page."""
    from test_connectors import WD, workday_sources

    company_id = db.upsert_company(conn, "Sun Life", canadian=True)
    db.upsert_board(conn, company_id, "workday", WD)
    run_scan(conn, settings, transport=workday_sources().transport())
    job_id = conn.execute("SELECT id FROM jobs WHERE external_id = 'Data-Scientist_JR00128241'").fetchone()[0]
    assert [l.city for l in db.job_locations(conn, job_id)] == ["Toronto", "Waterloo"]

    sources = workday_sources()
    run_scan(conn, settings, transport=sources.transport())
    assert not [r for r in sources.requests if r.method == "GET" and "Data-Scientist_JR00128241" in str(r.url)
                and "Senior" not in str(r.url)]
    assert [l.city for l in db.job_locations(conn, job_id)] == ["Toronto", "Waterloo"]


def test_source_terms(conn, settings):
    assert source_terms(conn, settings) == settings.workday.search_terms
    conn.execute("INSERT INTO saved_searches (name, query, use_for_sources) VALUES "
                 "('ai', '\"machine learning\" OR llm*', 1), ('mine', 'python', 0), ('data', 'data analyst', 1)")
    assert source_terms(conn, settings) == ["machine learning", "llm", "data analyst"]
