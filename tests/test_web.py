from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from jobradar import cli, db, tracking
from jobradar.boards import BoardError, normalize_board
from jobradar.models import Location, RawJob
from jobradar.web import app as web_app

from conftest import FakeSources

GH = "https://boards-api.greenhouse.io/v1/boards/"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "web.db"


def make_client(settings, db_path, sources=None):
    app = web_app.create_app(settings, db_path, transport=sources.transport() if sources else None)
    return TestClient(app)


@pytest.fixture
def client(settings, db_path):
    return make_client(settings, db_path)


@pytest.fixture
def seeded(settings, db_path):
    """Two companies, five jobs; returns a client and the ids by name."""
    conn = db.connect(db_path)
    cohere = db.upsert_company(conn, "Cohere", canadian=True)
    conn.execute("UPDATE companies SET employee_count = 500 WHERE id = ?", (cohere,))
    big = db.upsert_company(conn, "Big Bank", canadian=True)
    conn.execute("UPDATE companies SET employee_count = 40000 WHERE id = ?", (big,))
    b1 = db.upsert_board(conn, cohere, "ashby", "cohere")
    b2 = db.upsert_board(conn, big, "workday", "https://bank.wd3.myworkdayjobs.com/Careers")
    today = datetime.now(UTC).date()
    jobs = [
        (b1, "1", "Machine Learning Engineer", [Location("Toronto", "ON", "CA")], today, "CA$150K", "hybrid"),
        (b1, "2", "Data Analyst", [Location("Vancouver", "BC", "CA")], today - timedelta(days=40), None, "onsite"),
        (b1, "3", "Applied AI Engineer", [Location(None, None, "CA", remote=True, raw="Remote (Canada)")],
         today - timedelta(days=3), None, "remote"),
        (b2, "4", "Data Engineer, analytics", [Location("Toronto", "ON", "CA")], today - timedelta(days=1), None, "unknown"),
        (b2, "5", "Teller", [Location("New York", "NY", "US")], today, None, "onsite"),  # never shown
    ]
    ids = {}
    for board, ext, title, locs, posted, salary, workplace in jobs:
        job_id, _ = db.upsert_job(conn, board, RawJob(ext, title, f"https://x/{ext}", locs,
                                                      posted_at=posted.isoformat(), salary_text=salary,
                                                      workplace=workplace, description=f"About {title}"))
        ids[title] = job_id
    ids["cohere"], ids["big"], ids["board_cohere"] = cohere, big, b1
    conn.close()
    return make_client(settings, db_path), ids


def titles(response):
    assert response.status_code == 200, response.text
    return sorted(j["title"] for j in response.json()["items"])


# --- empty database --------------------------------------------------------------------

def test_empty_database(client):
    meta = client.get("/api/meta").json()
    assert meta["open_jobs"] == 0 and meta["companies"] == 0
    assert {"code": "ON", "name": "Ontario"} in meta["provinces"]
    assert "unknown" in meta["size_bands"] and "applied" in meta["job_statuses"]
    assert client.get("/api/jobs").json() == {"total": 0, "page": 1, "page_size": 50, "items": []}
    assert client.get("/api/companies").json() == []
    assert client.get("/api/scans").json() == []
    assert client.get("/api/saved-searches").json() == []


def test_unknown_api_path_is_404_json(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "no API endpoint /api/nope"


# --- jobs ---------------------------------------------------------------------------

def test_jobs_never_outside_canada(seeded):
    client, _ = seeded
    assert "Teller" not in titles(client.get("/api/jobs?include_closed=1"))
    assert client.get("/api/meta").json()["open_jobs"] == 4


def test_job_summary_fields(seeded):
    client, ids = seeded
    job = next(j for j in client.get("/api/jobs").json()["items"] if j["id"] == ids["Machine Learning Engineer"])
    assert job["company"] == "Cohere"
    assert job["location"] == "Toronto, ON"
    assert job["provinces"] == ["ON"]
    assert job["size_band"] == "200-999"
    assert job["salary"] == "CA$150K"
    assert job["status"] == "new"


@pytest.mark.parametrize("params,expected", [
    ("q=engineer", ["Applied AI Engineer", "Data Engineer, analytics", "Machine Learning Engineer"]),
    ("q=analytics", ["Data Engineer, analytics"]),
    ("q=about&title_only=1", []),
    ("q=analy*&title_only=1", ["Data Analyst", "Data Engineer, analytics"]),
    ("provinces=ON", ["Data Engineer, analytics", "Machine Learning Engineer"]),
    ("provinces=BC,REMOTE", ["Applied AI Engineer", "Data Analyst"]),
    ("sizes=5000%2B", ["Data Engineer, analytics"]),
    ("sizes=200-999", ["Applied AI Engineer", "Data Analyst", "Machine Learning Engineer"]),
    ("sizes=unknown", []),
    ("posted_within=7", ["Applied AI Engineer", "Data Engineer, analytics", "Machine Learning Engineer"]),
    ("systems=workday", ["Data Engineer, analytics"]),
    ("workplaces=remote,hybrid", ["Applied AI Engineer", "Machine Learning Engineer"]),
    ("has_salary=1", ["Machine Learning Engineer"]),
])
def test_job_filters(seeded, params, expected):
    client, _ = seeded
    assert titles(client.get(f"/api/jobs?{params}")) == expected


def test_province_counts(seeded):
    client, ids = seeded
    counts = client.get("/api/jobs/provinces").json()
    assert counts == {"ON": 2, "BC": 1, "REMOTE": 1}
    # Counts follow the other filters but not the province choice itself.
    assert client.get("/api/jobs/provinces?q=engineer&provinces=BC").json() == {"ON": 2, "REMOTE": 1}


def test_company_filter_and_status_filter(seeded):
    client, ids = seeded
    assert titles(client.get(f"/api/jobs?company={ids['big']}")) == ["Data Engineer, analytics"]
    client.patch(f"/api/jobs/{ids['Data Analyst']}", json={"status": "saved"})
    assert titles(client.get("/api/jobs?status=saved")) == ["Data Analyst"]


def test_ignored_company_hidden_by_default(seeded):
    client, ids = seeded
    client.patch(f"/api/companies/{ids['big']}", json={"status": "ignored"})
    assert "Data Engineer, analytics" not in titles(client.get("/api/jobs"))
    assert "Data Engineer, analytics" in titles(client.get("/api/jobs?include_ignored=1"))
    assert titles(client.get("/api/jobs?company_status=ignored")) == ["Data Engineer, analytics"]


def test_paging_and_sorting(seeded):
    client, _ = seeded
    first = client.get("/api/jobs?page_size=2&sort=title&order=asc").json()
    second = client.get("/api/jobs?page_size=2&page=2&sort=title&order=asc").json()
    assert first["total"] == 4
    assert [j["title"] for j in first["items"] + second["items"]] == [
        "Applied AI Engineer", "Data Analyst", "Data Engineer, analytics", "Machine Learning Engineer"]
    newest = client.get("/api/jobs").json()["items"]
    assert newest[-1]["title"] == "Data Analyst"  # oldest posting last


def test_bad_search_syntax_is_400(seeded):
    client, _ = seeded
    response = client.get('/api/jobs?q="unclosed')
    assert response.status_code == 400
    assert "search syntax" in response.json()["detail"]


def test_new_since(seeded, db_path):
    client, ids = seeded
    conn = db.connect(db_path)
    conn.execute("UPDATE jobs SET first_seen = '2026-01-01T00:00:00+00:00'")
    conn.execute("UPDATE jobs SET first_seen = '2026-10-26T12:00:00+00:00' WHERE id = ?", (ids["Data Analyst"],))
    conn.commit()
    assert titles(client.get("/api/jobs?new_since=2026-10-01T00:00:00%2B00:00")) == ["Data Analyst"]


def test_job_detail(seeded):
    client, ids = seeded
    job = client.get(f"/api/jobs/{ids['Machine Learning Engineer']}").json()
    assert job["description"] == "About Machine Learning Engineer"
    assert job["locations"][0]["label"] == "Toronto, ON"
    assert job["links"]["linkedin"].startswith("https://www.linkedin.com/jobs/search/?keywords=Machine+Learning")
    assert job["links"]["linkedin"].endswith("&location=Canada")
    assert client.get("/api/jobs/9999").status_code == 404


def test_status_change_sets_applied_at_and_history(seeded):
    client, ids = seeded
    job_id = ids["Data Analyst"]
    result = client.patch(f"/api/jobs/{job_id}", json={"status": "applied", "notes": "via referral"}).json()
    assert result["status"] == "applied"
    assert result["applied_at"] == datetime.now(UTC).date().isoformat()
    assert result["notes"] == "via referral"
    client.patch(f"/api/jobs/{job_id}", json={"status": "interviewing"})
    again = client.patch(f"/api/jobs/{job_id}", json={"status": "applied"}).json()
    assert again["applied_at"] == result["applied_at"]  # first date kept
    events = client.get(f"/api/jobs/{job_id}").json()["events"]
    assert [(e["old"], e["new"]) for e in events] == [("new", "applied"), ("applied", "interviewing"),
                                                      ("interviewing", "applied")]


def test_applied_at_editable_and_clearable(seeded):
    client, ids = seeded
    job_id = ids["Data Analyst"]
    client.patch(f"/api/jobs/{job_id}", json={"status": "applied", "applied_at": "2026-10-01"})
    assert client.get(f"/api/jobs/{job_id}").json()["applied_at"] == "2026-10-01"
    client.patch(f"/api/jobs/{job_id}", json={"applied_at": None})
    assert client.get(f"/api/jobs/{job_id}").json()["applied_at"] is None


def test_bad_job_patch(seeded):
    client, ids = seeded
    assert client.patch(f"/api/jobs/{ids['Data Analyst']}", json={"status": "maybe"}).status_code == 400
    assert client.patch("/api/jobs/9999", json={"notes": "x"}).status_code == 404


def test_export_csv_follows_filters(seeded):
    client, _ = seeded
    response = client.get("/api/jobs.csv?provinces=ON")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert len(lines) == 3  # header + 2 Ontario jobs
    assert "Teller" not in response.text


# --- companies and boards --------------------------------------------------------------

def test_companies_list(seeded):
    client, _ = seeded
    rows = {c["name"]: c for c in client.get("/api/companies").json()}
    assert rows["Cohere"]["canada_open"] == 3
    assert rows["Big Bank"]["canada_open"] == 1  # the New York job isn't counted
    assert rows["Cohere"]["boards"][0]["system"] == "ashby"
    assert [c["name"] for c in client.get("/api/companies?sizes=5000%2B").json()] == ["Big Bank"]
    assert [c["name"] for c in client.get("/api/companies?q=coh").json()] == ["Cohere"]


def test_manual_size_and_status(seeded):
    client, ids = seeded
    company = client.patch(f"/api/companies/{ids['cohere']}", json={"employee_count": 30, "notes": "AI lab",
                                                                     "status": "target"}).json()
    assert (company["size_band"], company["size_source"], company["status"], company["notes"]) == \
        ("<50", "manual", "target", "AI lab")
    cleared = client.patch(f"/api/companies/{ids['cohere']}", json={"employee_count": None}).json()
    assert (cleared["employee_count"], cleared["size_band"]) == (None, "unknown")
    assert client.patch(f"/api/companies/{ids['cohere']}", json={"status": "fav"}).status_code == 400
    assert client.patch(f"/api/companies/{ids['cohere']}", json={"employee_count": -1}).status_code == 400


def test_add_company_with_pasted_board_url(client):
    response = client.post("/api/companies", json={
        "name": "Docebo", "canadian": True, "board": {"system": "ashby", "slug_or_url": "https://jobs.ashbyhq.com/docebo"}})
    assert response.status_code == 201
    assert response.json()["boards"][0]["slug_or_url"] == "docebo"
    assert client.post("/api/companies", json={"name": "docebo"}).status_code == 409
    bad = client.post("/api/companies", json={"name": "X", "board": {"system": "lever", "slug_or_url": "https://example.com/x"}})
    assert bad.status_code == 400


def test_add_board_and_toggle(seeded):
    client, ids = seeded
    company = client.post(f"/api/companies/{ids['cohere']}/boards",
                          json={"system": "lever", "slug_or_url": "jobs.lever.co/cohere"}).json()
    lever = next(b for b in company["boards"] if b["system"] == "lever")
    assert lever["slug_or_url"] == "cohere"
    board = client.patch(f"/api/boards/{lever['id']}", json={"enabled": False}).json()
    assert board["enabled"] == 0
    conflict = client.post(f"/api/companies/{ids['big']}/boards", json={"system": "lever", "slug_or_url": "cohere"})
    assert conflict.status_code == 409


# --- saved searches -----------------------------------------------------------------

def test_saved_searches_crud(client):
    created = client.post("/api/saved-searches", json={
        "name": "AI in Ontario", "query": '"machine learning" OR llm', "filters": {"provinces": "ON"},
        "use_for_sources": True}).json()
    assert created["filters"] == {"provinces": "ON"} and created["use_for_sources"] is True
    renamed = client.patch(f"/api/saved-searches/{created['id']}", json={"name": "AI (ON)", "use_for_sources": False}).json()
    assert (renamed["name"], renamed["use_for_sources"]) == ("AI (ON)", False)
    assert client.post("/api/saved-searches", json={"name": "  "}).status_code == 400
    assert client.delete(f"/api/saved-searches/{created['id']}").status_code == 204
    assert client.get("/api/saved-searches").json() == []


# --- visits ---------------------------------------------------------------------------

def test_record_visit_groups_reloads(conn):
    t0 = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
    assert tracking.record_visit(conn, t0) is None
    assert tracking.record_visit(conn, t0 + timedelta(minutes=20)) is None  # same visit
    later = t0 + timedelta(hours=5)
    assert tracking.record_visit(conn, later) == (t0 + timedelta(minutes=20)).isoformat()
    # A reload during the second visit keeps the same baseline.
    assert tracking.record_visit(conn, later + timedelta(minutes=5)) == (t0 + timedelta(minutes=20)).isoformat()


def test_visit_endpoint(client):
    assert client.post("/api/visit").json() == {"previous": None}


# --- scans ---------------------------------------------------------------------------

def test_scan_now_runs_in_background(settings, db_path):
    conn = db.connect(db_path)
    acme = db.upsert_company(conn, "Acme", canadian=True)
    db.upsert_board(conn, acme, "greenhouse", "acme")
    conn.close()
    sources = FakeSources({("GET", GH + "acme"): {"jobs": [
        {"id": 1, "title": "Data Analyst", "absolute_url": "u", "location": {"name": "Toronto, ON"}}]}})
    client = make_client(settings, db_path, sources)

    started = client.post("/api/scans", json={})
    assert started.status_code == 202
    assert started.json()["boards_total"] == 1
    client.app.state.runner.wait(10)

    state = client.get("/api/scans/current").json()
    assert state["running"] is False and state["boards_done"] == 1 and state["jobs_new"] == 1
    assert state["recent"][0]["company"] == "Acme"
    history = client.get("/api/scans").json()
    assert len(history) == 1
    detail = client.get(f"/api/scans/{history[0]['id']}").json()
    assert detail["results"][0]["company"] == "Acme" and detail["results"][0]["ok"] == 1
    assert titles(client.get("/api/jobs")) == ["Data Analyst"]


def test_scan_one_company_and_conflicts(seeded):
    client, ids = seeded
    assert client.post("/api/scans", json={"company_id": 9999}).status_code == 404
    client.app.state.runner._state.running = True
    assert client.post("/api/scans", json={}).status_code == 409


# --- serving the UI -----------------------------------------------------------------

def test_ui_not_built_message(client, tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "STATIC_DIR", tmp_path / "nothing")
    response = client.get("/")
    assert response.status_code == 200 and "npm run build" in response.text


def test_ui_serves_files_and_falls_back_to_index(client, tmp_path, monkeypatch):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<div id=root></div>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("no")
    monkeypatch.setattr(web_app, "STATIC_DIR", static)
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/jobs/12").text == "<div id=root></div>"
    assert client.get("/../secret.txt").text != "no"


# --- boards helper and CLI -------------------------------------------------------------

@pytest.mark.parametrize("system,value,slug", [
    ("ashby", "cohere", "cohere"),
    ("ashby", "https://jobs.ashbyhq.com/docebo", "docebo"),
    ("greenhouse", "https://job-boards.greenhouse.io/stackadapt", "stackadapt"),
    ("greenhouse", "https://job-boards.greenhouse.io/embed/job_board?for=hootsuite", "hootsuite"),
    ("lever", "jobs.lever.co/cority", "cority"),
    ("bamboohr", "https://avidbots.bamboohr.com/careers", "avidbots"),
    ("recruitee", "https://petalmd.recruitee.com/", "petalmd"),
    ("rippling", "https://ats.rippling.com/paper-careers/jobs", "paper-careers"),
    ("workday", "https://bb.wd3.myworkdayjobs.com/en-US/BlackBerry/", "https://bb.wd3.myworkdayjobs.com/BlackBerry"),
])
def test_normalize_board(system, value, slug):
    assert normalize_board(system, value) == slug


@pytest.mark.parametrize("system,value", [
    ("ashby", "https://jobs.lever.co/x"), ("taleo", "x"), ("lever", ""), ("workday", "https://example.com/x"),
])
def test_normalize_board_errors(system, value):
    with pytest.raises(BoardError):
        normalize_board(system, value)


def test_serve_dev_needs_npm_packages(tmp_path, capsys):
    assert cli.main(["--root", str(tmp_path), "serve", "--dev"]) == 1
    assert "npm install" in capsys.readouterr().err
