import sqlite3

import pytest

from jobradar import db
from jobradar.models import Location, RawJob


def make_job(external_id="1", title="Machine Learning Engineer", **kw):
    kw.setdefault("url", f"https://example.com/{external_id}")
    kw.setdefault("locations", [Location("Toronto", "ON", "CA")])
    return RawJob(external_id=external_id, title=title, **kw)


@pytest.fixture
def board(conn):
    company_id = db.upsert_company(conn, "Cohere", canadian=True)
    return db.upsert_board(conn, company_id, "ashby", "cohere")


def test_migrations_on_empty_file(tmp_path):
    conn = db.connect(tmp_path / "new.db")
    assert db.schema_version(conn) == len(db.MIGRATIONS)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"companies", "boards", "jobs", "job_locations", "jobs_fts", "scans",
            "scan_results", "saved_searches", "settings"} <= tables


def test_upgrade_from_version_2_keeps_data(tmp_path):
    """The real database was created at version 2; migration 3 rebuilds companies."""
    import sqlite3 as sq

    path = tmp_path / "old.db"
    old = sq.connect(path)
    for number, script in enumerate(db.MIGRATIONS[:2], start=1):
        old.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute("PRAGMA foreign_keys = ON")
    old.execute("INSERT INTO companies (id, name, canadian, status, notes, employee_count, size_source, created_at) "
                "VALUES (1, 'Cohere', 1, 'target', 'dream', 500, 'manual', 'x')")
    old.execute("INSERT INTO boards (id, company_id, system, slug_or_url) VALUES (1, 1, 'ashby', 'cohere')")
    old.execute("INSERT INTO jobs (id, board_id, external_id, title, url, first_seen, last_seen) "
                "VALUES (1, 1, 'a', 'ML Engineer', 'u', 'x', 'x')")
    old.commit()
    old.close()

    conn = db.connect(path)
    assert db.schema_version(conn) == len(db.MIGRATIONS)
    row = conn.execute("SELECT * FROM companies").fetchone()
    assert (row["name"], row["status"], row["notes"], row["employee_count"], row["size_source"]) == \
        ("Cohere", "target", "dream", 500, "manual")
    assert row["hq_country"] is None
    # Triggers still work after the rebuild: new jobs are searchable, renames follow.
    db.upsert_job(conn, 1, RawJob("b", "Data Analyst", "u2"))
    assert [r["title"] for r in db.search_jobs(conn, "cohere")] == ["ML Engineer", "Data Analyst"]
    conn.execute("UPDATE companies SET name = 'Cohere AI' WHERE id = 1")
    assert len(db.search_jobs(conn, '"cohere ai"')) == 2
    conn.execute("UPDATE companies SET size_source = 'imported' WHERE id = 1")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reconnect_does_not_rerun_migrations(tmp_path):
    path = tmp_path / "again.db"
    db.connect(path).close()
    conn = db.connect(path)
    assert db.schema_version(conn) == len(db.MIGRATIONS)


def test_creates_parent_folder(tmp_path):
    db.connect(tmp_path / "data" / "deep" / "x.db").close()
    assert (tmp_path / "data" / "deep" / "x.db").exists()


def test_upsert_company_is_idempotent_and_keeps_tracking(conn):
    first = db.upsert_company(conn, "Cohere", canadian=True)
    conn.execute("UPDATE companies SET status = 'target', notes = 'dream job' WHERE id = ?", (first,))
    second = db.upsert_company(conn, "cohere", canadian=True)  # name match ignores case
    assert first == second
    row = conn.execute("SELECT * FROM companies").fetchall()
    assert len(row) == 1
    assert (row[0]["status"], row[0]["notes"]) == ("target", "dream job")


def test_upsert_board_never_unconfirms(conn):
    company_id = db.upsert_company(conn, "Maple")
    board_id = db.upsert_board(conn, company_id, "ashby", "maple", confirmed=False)
    conn.execute("UPDATE boards SET confirmed = 1 WHERE id = ?", (board_id,))
    assert db.upsert_board(conn, company_id, "ashby", "maple", confirmed=False) == board_id
    assert conn.execute("SELECT confirmed FROM boards").fetchone()[0] == 1


def test_upsert_board_enabled_only_when_given(conn):
    company_id = db.upsert_company(conn, "Acme")
    board_id = db.upsert_board(conn, company_id, "lever", "acme")
    db.upsert_board(conn, company_id, "lever", "acme", enabled=False)
    assert conn.execute("SELECT enabled FROM boards WHERE id = ?", (board_id,)).fetchone()[0] == 0
    db.upsert_board(conn, company_id, "lever", "acme")  # not given: unchanged
    assert conn.execute("SELECT enabled FROM boards WHERE id = ?", (board_id,)).fetchone()[0] == 0


def test_status_check_constraint(conn, board):
    job_id, _ = db.upsert_job(conn, board, make_job())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE jobs SET status = 'maybe' WHERE id = ?", (job_id,))


def test_upsert_job_new_then_seen_again(conn, board):
    job_id, is_new = db.upsert_job(conn, board, make_job(), seen_at="2026-10-01T00:00:00+00:00")
    assert is_new
    conn.execute(
        "UPDATE jobs SET status = 'applied', notes = 'sent CV', closed_at = 'x' WHERE id = ?",
        (job_id,),
    )
    again_id, is_new = db.upsert_job(
        conn, board, make_job(title="ML Engineer II"), seen_at="2026-10-02T00:00:00+00:00"
    )
    assert (again_id, is_new) == (job_id, False)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    assert row["title"] == "ML Engineer II"
    assert row["first_seen"] == "2026-10-01T00:00:00+00:00"
    assert row["last_seen"] == "2026-10-02T00:00:00+00:00"
    assert row["closed_at"] is None  # reopened
    assert (row["status"], row["notes"]) == ("applied", "sent CV")  # tracking kept


def test_job_locations_replaced(conn, board):
    job_id, _ = db.upsert_job(conn, board, make_job())
    db.upsert_job(conn, board, make_job(locations=[Location(None, None, "CA", remote=True, raw="Remote")]))
    assert db.job_locations(conn, job_id) == [Location(None, None, "CA", True, "Remote")]


def test_fts_finds_title_company_and_description(conn, board):
    db.upsert_job(conn, board, make_job("1", "Machine Learning Engineer", description="PyTorch and LLMs"))
    db.upsert_job(conn, board, make_job("2", "Data Analyst", description="SQL, dbt and Looker"))
    assert [r["title"] for r in db.search_jobs(conn, '"machine learning"')] == ["Machine Learning Engineer"]
    assert [r["title"] for r in db.search_jobs(conn, "dbt")] == ["Data Analyst"]
    assert {r["title"] for r in db.search_jobs(conn, "cohere")} == {"Machine Learning Engineer", "Data Analyst"}
    assert [r["title"] for r in db.search_jobs(conn, "analy*")] == ["Data Analyst"]
    assert len(db.search_jobs(conn, "engineer OR analyst")) == 2


def test_fts_ignores_accents(conn, board):
    db.upsert_job(conn, board, make_job("3", "Ingénieur IA Appliquée"))
    assert [r["title"] for r in db.search_jobs(conn, "ingenieur")] == ["Ingénieur IA Appliquée"]


def test_fts_follows_title_update_and_company_rename(conn, board):
    db.upsert_job(conn, board, make_job("1", "Data Analyst"))
    db.upsert_job(conn, board, make_job("1", "Data Scientist"))
    assert db.search_jobs(conn, "analyst") == []
    assert len(db.search_jobs(conn, "scientist")) == 1
    conn.execute("UPDATE companies SET name = 'Cohere AI'")
    assert len(db.search_jobs(conn, '"cohere ai"')) == 1


def test_list_companies_summarizes_boards(conn):
    company_id = db.upsert_company(conn, "D2L", canadian=True)
    db.upsert_board(conn, company_id, "greenhouse", "d2l")
    db.upsert_board(conn, company_id, "lever", "d2l", confirmed=False)
    db.upsert_company(conn, "Alone")
    rows = {r["name"]: r for r in db.list_companies(conn)}
    assert rows["D2L"]["board_count"] == 2
    assert "lever:d2l (unconfirmed)" in rows["D2L"]["boards"]
    assert rows["Alone"]["board_count"] == 0


def test_settings_roundtrip(conn):
    assert db.get_setting(conn, "last_visit_at", "never") == "never"
    db.set_setting(conn, "last_visit_at", "2026-10-26T10:00:00+00:00")
    db.set_setting(conn, "last_visit_at", "2026-10-27T10:00:00+00:00")
    assert db.get_setting(conn, "last_visit_at") == "2026-10-27T10:00:00+00:00"


def test_connection_can_be_closed_from_another_thread(tmp_path):
    """The web app opens a request's connection on one worker thread and FastAPI
    may close it on another; that must not raise."""
    import threading

    conn = db.connect(tmp_path / "threads.db")
    errors = []

    def close():
        try:
            conn.execute("SELECT 1").fetchone()
            conn.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    worker = threading.Thread(target=close)
    worker.start()
    worker.join()
    assert errors == []
