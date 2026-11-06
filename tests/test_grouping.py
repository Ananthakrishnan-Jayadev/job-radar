"""One job posted for several places shows once; stray commas in places are cleaned."""

from fastapi.testclient import TestClient

from jobradar import db, queries, tracking
from jobradar.locations import from_parts
from jobradar.models import Location, RawJob
from jobradar.web import app as web_app


def _post(conn, board, ext, title, city, province="ON", posted="2026-11-01"):
    return db.upsert_job(conn, board, RawJob(ext, title, f"https://x/{ext}", [Location(city, province, "CA")],
                                             posted_at=posted))[0]


def _setup(conn):
    acme = db.upsert_company(conn, "Acme", canadian=True)
    other = db.upsert_company(conn, "Other", canadian=True)
    a = db.upsert_board(conn, acme, "ashby", "acme")
    o = db.upsert_board(conn, other, "ashby", "other")
    ids = {
        "toronto": _post(conn, a, "1", "Data Engineer", "Toronto"),
        "ottawa": _post(conn, a, "2", "data engineer ", "Ottawa", posted="2026-11-03"),
        "montreal": _post(conn, a, "3", "Data Engineer", "Montreal", "QC"),
        "analyst": _post(conn, a, "4", "Data Analyst", "Toronto", posted="2026-10-20"),
        # Same title at another company: never grouped with Acme's.
        "other": _post(conn, o, "5", "Data Engineer", "Toronto", posted="2026-10-25"),
    }
    return ids


def test_same_company_same_title_is_one_row(conn):
    ids = _setup(conn)
    total, rows = queries.search_jobs(conn, queries.JobFilter(all_roles=True), group=True)
    assert total == 3
    assert [(r["company"], r["title"].strip().lower()) for r in rows] == [
        ("Acme", "data engineer"), ("Other", "data engineer"), ("Acme", "data analyst")]
    group = rows[0]["group"]
    assert sorted(m["id"] for m in group) == sorted([ids["toronto"], ids["ottawa"], ids["montreal"]])
    assert {queries.location_label(m["locations"]) for m in group} == {"Toronto, ON", "Ottawa, ON", "Montreal, QC"}
    assert rows[1]["group"] is None and rows[2]["group"] is None
    # Ungrouped, every posting is its own row.
    assert queries.search_jobs(conn, queries.JobFilter(all_roles=True))[0] == 5


def test_group_shows_a_decided_job_and_follows_the_filter(conn):
    ids = _setup(conn)
    tracking.update_job(conn, ids["montreal"], status="saved")
    _, rows = queries.search_jobs(conn, queries.JobFilter(all_roles=True), group=True)
    assert rows[0]["id"] == ids["montreal"]  # the saved one represents the group
    # Filtered to Ontario, Montreal's copy isn't part of the group.
    _, rows = queries.search_jobs(conn, queries.JobFilter(all_roles=True, provinces=["ON"]), group=True)
    acme = next(r for r in rows if r["company"] == "Acme" and r["group"])
    assert sorted(m["id"] for m in acme["group"]) == sorted([ids["toronto"], ids["ottawa"]])


def test_province_counts_count_a_group_once(conn):
    _setup(conn)
    counts = queries.province_counts(conn, queries.JobFilter(all_roles=True))
    assert counts["ON"] == 3  # Acme's engineer (twice in Ontario), Acme's analyst, Other's engineer
    assert counts["QC"] == 1


def test_jobs_api_groups_unless_asked_not_to(settings, tmp_path):
    db_path = tmp_path / "web.db"
    conn = db.connect(db_path)
    _setup(conn)
    conn.close()
    client = TestClient(web_app.create_app(settings, db_path))
    body = client.get("/api/jobs?all_roles=1").json()
    assert body["total"] == 3
    first = body["items"][0]
    assert len(first["group"]) == 3 and {"id", "url", "status", "location"} <= set(first["group"][0])
    assert client.get("/api/jobs?all_roles=1&group=0").json()["total"] == 5


def test_from_parts_cleans_stray_commas():
    loc = from_parts("Mississauga,", "Ontario", "Canada")
    assert (loc.city, loc.province, loc.label()) == ("Mississauga", "ON", "Mississauga, ON")
    loc = from_parts("Brampton, Ontario", "", "Canada")
    assert (loc.city, loc.province) == ("Brampton", "ON")


def test_stored_places_are_tidied_once(tmp_path):
    path = tmp_path / "old.db"
    conn = db.connect(path)
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "ashby", "acme")
    job = _post(conn, board, "1", "Analyst", "Toronto")
    with conn:
        conn.execute("UPDATE job_locations SET city = 'Mississauga,' WHERE job_id = ?", (job,))
        conn.execute("DELETE FROM settings WHERE key = 'locations_tidied_v1'")
    conn.close()
    conn = db.connect(path)
    assert conn.execute("SELECT city FROM job_locations").fetchone()[0] == "Mississauga"
    conn.close()
