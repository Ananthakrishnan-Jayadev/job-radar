"""Hiding roles roles.toml doesn't want: sync, queries, API, CLI."""

from fastapi.testclient import TestClient

from jobradar import cli, db, queries
from jobradar.models import Location, RawJob
from jobradar.roles import sync_roles
from jobradar.web import app as web_app

ROLES = """
[categories.software]
label = "Software"
include = ['software', 'developer']
[categories.data]
label = "Data"
include = ['data analyst']
[categories.adjacent]
label = "Adjacent"
enabled = false
include = ['business analyst']
[rules]
exclude = ['financial advisor']
"""


def setup(conn, tmp_path, roles=ROLES):
    (tmp_path / "roles.toml").write_text(roles)
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "ashby", "acme")
    ids = {}
    for ext, title in (("1", "Software Engineer"), ("2", "Data Analyst"), ("3", "Business Analyst"),
                       ("4", "Financial Advisor"), ("5", "Barista")):
        ids[title], _ = db.upsert_job(conn, board, RawJob(ext, title, f"u{ext}", [Location("Toronto", "ON", "CA")]))
    conn.commit()
    return ids


def titles(rows):
    return sorted(r["title"] for r in rows)


def test_sync_and_default_filter(conn, tmp_path):
    setup(conn, tmp_path)
    assert sync_roles(conn, tmp_path) == 5
    assert titles(queries.find_jobs(conn)) == ["Data Analyst", "Software Engineer"]
    assert len(queries.find_jobs(conn, all_roles=True)) == 5
    cats = dict(conn.execute("SELECT title, role_categories FROM jobs"))
    assert (cats["Software Engineer"], cats["Business Analyst"], cats["Barista"]) == (",software,", ",adjacent,", "")


def test_only_new_jobs_are_redone_until_the_file_changes(conn, tmp_path):
    setup(conn, tmp_path)
    sync_roles(conn, tmp_path)
    assert sync_roles(conn, tmp_path) == 0  # nothing changed
    (tmp_path / "roles.toml").write_text(ROLES.replace("enabled = false", "enabled = true"))
    assert sync_roles(conn, tmp_path) == 5  # file changed: everything redone
    assert "Business Analyst" in titles(queries.find_jobs(conn))


def test_tracked_jobs_always_show(conn, tmp_path):
    ids = setup(conn, tmp_path)
    sync_roles(conn, tmp_path)
    conn.execute("UPDATE jobs SET status = 'applied' WHERE id = ?", (ids["Barista"],))
    conn.commit()
    assert "Barista" in titles(queries.find_jobs(conn))


def test_without_roles_file_everything_shows(conn, tmp_path):
    setup(conn, tmp_path)
    sync_roles(conn, tmp_path)
    (tmp_path / "roles.toml").unlink()
    sync_roles(conn, tmp_path)
    assert len(queries.find_jobs(conn)) == 5


def test_category_filter_and_company_counts(conn, tmp_path):
    setup(conn, tmp_path)
    sync_roles(conn, tmp_path)
    f = queries.JobFilter(role_categories=["adjacent"], include_ignored=True)
    assert titles(queries.search_jobs(conn, f)[1]) == ["Business Analyst"]
    company = queries.list_companies(conn)[0]
    assert (company["canada_open"], company["wanted_open"]) == (5, 2)


def test_api_hides_and_shows(settings, tmp_path):
    settings.root = tmp_path
    conn = db.connect(tmp_path / "w.db")
    setup(conn, tmp_path)
    conn.close()
    client = TestClient(web_app.create_app(settings, tmp_path / "w.db"))
    assert client.get("/api/jobs").json()["total"] == 2
    assert client.get("/api/jobs?all_roles=1").json()["total"] == 5
    assert [j["title"] for j in client.get("/api/jobs?roles=data").json()["items"]] == ["Data Analyst"]
    job = next(j for j in client.get("/api/jobs").json()["items"] if j["title"] == "Software Engineer")
    assert job["roles"] == ["software"]
    meta = client.get("/api/meta").json()
    assert {"name": "adjacent", "label": "Adjacent", "enabled": False} in meta["role_categories"]
    assert meta["open_jobs"] == 2
    assert client.get("/api/companies").json()[0]["wanted_open"] == 2
    assert client.get("/api/jobs/provinces").json()["ON"] == 2
    assert client.get("/api/jobs.csv").text.count("\n") == 3  # header + 2


def test_cli_all_roles(tmp_path, capsys):
    conn = db.connect(tmp_path / "c.db")
    setup(conn, tmp_path)
    conn.close()
    args = ["--root", str(tmp_path), "--db", str(tmp_path / "c.db"), "search"]
    assert cli.main(args) == 0
    assert "2 jobs" in capsys.readouterr().out
    assert cli.main(args + ["--all-roles"]) == 0
    assert "5 jobs" in capsys.readouterr().out
