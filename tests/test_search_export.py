import csv

import pytest

from jobradar import cli, db, queries
from jobradar.export import export_jobs
from jobradar.models import Location, RawJob


@pytest.fixture
def jobs(conn):
    company = db.upsert_company(conn, "Cohere", canadian=True)
    conn.execute("UPDATE companies SET employee_count = 500 WHERE id = ?", (company,))
    board = db.upsert_board(conn, company, "ashby", "cohere")
    rows = [
        ("1", "Machine Learning Engineer", [Location("Toronto", "ON", "CA")], "2026-10-20"),
        ("2", "Data Analyst", [Location("Vancouver", "BC", "CA")], "2026-10-22"),
        ("3", "Applied AI Engineer", [Location(None, None, "CA", remote=True, raw="Remote (Canada)")], "2026-10-21"),
        ("4", "Data Scientist", [Location("Montréal", "QC", "CA"), Location("Toronto", "ON", "CA")], None),
    ]
    for ext, title, locations, posted in rows:
        db.upsert_job(conn, board, RawJob(ext, title, f"https://x/{ext}", locations, posted_at=posted,
                                          salary_text="CA$100K" if ext == "1" else None))
    conn.execute("UPDATE jobs SET closed_at = '2026-10-25' WHERE external_id = '2'")
    conn.commit()  # the CLI opens its own connection, which also writes
    return conn


def titles(rows):
    return [r["title"] for r in rows]


def add(conn, ext, title, locations):
    board = conn.execute("SELECT id FROM boards").fetchone()[0]
    db.upsert_job(conn, board, RawJob(ext, title, f"https://x/{ext}", locations))


def test_never_shows_jobs_outside_canada(jobs):
    add(jobs, "9", "Dubai Sales", [Location("Dubai", None, None, remote=True, raw="Dubai")])
    add(jobs, "10", "NYC Sales", [Location("New York", "NY", "US")])
    add(jobs, "11", "Bare Remote", [Location(remote=True, raw="Remote")])
    found = titles(queries.find_jobs(jobs, include_closed=True))
    assert "Dubai Sales" not in found and "NYC Sales" not in found
    assert "Bare Remote" in found
    assert "Bare Remote" in titles(queries.find_jobs(jobs, provinces=["REMOTE"]))
    assert "Bare Remote" not in titles(queries.find_jobs(jobs, provinces=["ON"]))


def test_label_names_only_canadian_places():
    locs = [Location("Toronto", "ON", "CA"), Location("Dallas", "TX", "US"), Location("Phoenix", "AZ", "US")]
    assert queries.location_label(locs) == "Toronto, ON (+2 outside Canada)"
    assert queries.location_label([Location(remote=True, raw="Remote")]) == "Remote (country not stated)"


def test_find_all_open_newest_first(jobs):
    assert titles(queries.find_jobs(jobs)) == ["Data Scientist", "Applied AI Engineer", "Machine Learning Engineer"]


def test_find_include_closed(jobs):
    assert "Data Analyst" in titles(queries.find_jobs(jobs, include_closed=True))


def test_find_by_province(jobs):
    assert sorted(titles(queries.find_jobs(jobs, provinces=["ON"]))) == ["Data Scientist", "Machine Learning Engineer"]
    assert titles(queries.find_jobs(jobs, provinces=["qc"])) == ["Data Scientist"]
    assert titles(queries.find_jobs(jobs, provinces=["REMOTE"])) == ["Applied AI Engineer"]
    assert len(queries.find_jobs(jobs, provinces=["ON", "REMOTE"])) == 3
    assert queries.find_jobs(jobs, provinces=["BC"]) == []  # the BC job is closed


def test_find_by_query_and_province(jobs):
    assert titles(queries.find_jobs(jobs, "engineer", provinces=["ON"])) == ["Machine Learning Engineer"]
    assert titles(queries.find_jobs(jobs, "data", provinces=["QC"])) == ["Data Scientist"]


def test_locations_attached(jobs):
    row = next(r for r in queries.find_jobs(jobs) if r["title"] == "Data Scientist")
    assert queries.location_label(row["locations"]) == "Montréal, QC; Toronto, ON"


def test_export_csv(jobs, tmp_path):
    out = tmp_path / "jobs.csv"
    assert export_jobs(jobs, out, provinces=["ON"]) == 2
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    ml = next(r for r in rows if r["title"] == "Machine Learning Engineer")
    assert ml["company"] == "Cohere"
    assert ml["location"] == "Toronto, ON"
    assert ml["salary"] == "CA$100K"
    assert ml["company_size"] == "200-999"
    assert ml["status"] == "new"
    assert next(r for r in rows if r["title"] == "Data Scientist")["provinces"] == "ON,QC"


def test_cli_search_and_export(jobs, tmp_path, capsys):
    db_path = jobs.execute("PRAGMA database_list").fetchone()["file"]
    assert cli.main(["--db", db_path, "search", "machine", "learning", "--province", "ON"]) == 0
    out = capsys.readouterr().out
    assert "Machine Learning Engineer  |  Cohere  |  Toronto, ON  |  2026-10-20" in out
    assert "1 jobs" in out

    assert cli.main(["--db", db_path, "search", '"unclosed']) == 1
    assert "Search failed" in capsys.readouterr().err

    out_file = tmp_path / "all.csv"
    assert cli.main(["--db", db_path, "export", "--out", str(out_file), "--include-closed"]) == 0
    assert "Wrote 4 jobs" in capsys.readouterr().out
