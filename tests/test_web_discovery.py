"""Phase 4 endpoints: candidates, detection, sizes."""

import httpx
from fastapi.testclient import TestClient

from jobradar import db
from jobradar.sources import stillhiring
from jobradar.web import app as web_app

from conftest import FIXTURES, FakeSources, fixture_json
from test_discovery import WIKI, wikidata_reply


def sources_for_phase4():
    return FakeSources({
        ("GET", stillhiring.EMBED_URL): httpx.Response(200, text=(FIXTURES / "stillhiring_embed.html").read_text()),
        ("GET", "https://airtable.com/v0.3/view/"): fixture_json("stillhiring_view.json"),
        ("GET", WIKI): wikidata_reply(),
        ("GET", "https://www.shopify.com/careers"): httpx.Response(
            200, text='<a href="https://job-boards.greenhouse.io/shopify">Jobs</a>'),
    })


def client_for(settings, tmp_path, sources=None):
    app = web_app.create_app(settings, tmp_path / "p4.db", transport=(sources or sources_for_phase4()).transport())
    return TestClient(app)


def test_refresh_and_list_candidates(settings, tmp_path):
    client = client_for(settings, tmp_path)
    summary = client.post("/api/candidates/refresh").json()
    assert summary["total"] == 12 and summary["new"] == 12
    data = client.get("/api/candidates").json()
    assert data["refreshed_at"]
    names = [c["name"] for c in data["items"]]
    assert "Docebo" in names and "EDB" not in names
    docebo = next(c for c in data["items"] if c["name"] == "Docebo")
    assert (docebo["detected_system"], docebo["size_band"], docebo["hq_city"]) == ("ashby", "1000-4999", "Toronto")
    readable = [c["name"] for c in client.get("/api/candidates?scope=readable").json()["items"]]
    assert "LaunchDarkly" in readable


def test_refresh_failure_is_502(settings, tmp_path):
    sources = FakeSources({("GET", stillhiring.EMBED_URL): httpx.Response(200, text="<html>changed</html>")})
    client = client_for(settings, tmp_path, sources)
    response = client.post("/api/candidates/refresh")
    assert response.status_code == 502
    assert "couldn't be read" in response.json()["detail"]


def test_approve_reject_restore(settings, tmp_path):
    client = client_for(settings, tmp_path)
    client.post("/api/candidates/refresh")
    items = {c["name"]: c for c in client.get("/api/candidates").json()["items"]}
    company_id = client.post(f"/api/candidates/{items['Docebo']['id']}/approve").json()["company_id"]
    company = client.get(f"/api/companies/{company_id}").json()
    assert company["employee_count"] == 1009 and company["size_source"] == "stillhiring"
    assert company["hq"] == "Toronto, ON, CA"
    assert company["boards"][0]["slug_or_url"] == "docebo"

    petal = items["Petal"]["id"]
    assert client.post(f"/api/candidates/{petal}/reject").status_code == 200
    assert "Petal" in [c["name"] for c in client.get("/api/candidates?decision=rejected").json()["items"]]
    client.post(f"/api/candidates/{petal}/restore")
    assert "Petal" in [c["name"] for c in client.get("/api/candidates").json()["items"]]
    assert client.post("/api/candidates/9999/approve").status_code == 404


def test_detect_candidate_from_careers_page(settings, tmp_path):
    client = client_for(settings, tmp_path)
    client.post("/api/candidates/refresh")
    shopify = next(c for c in client.get("/api/candidates").json()["items"] if c["name"] == "Shopify")
    options = client.post(f"/api/candidates/{shopify['id']}/detect").json()["options"]
    assert options[0]["system"] == "greenhouse" and options[0]["slug_or_url"] == "shopify"
    refreshed = next(c for c in client.get("/api/candidates").json()["items"] if c["name"] == "Shopify")
    assert refreshed["detected_system"] == "greenhouse"


def test_detect_all_in_background(settings, tmp_path):
    client = client_for(settings, tmp_path)
    client.post("/api/candidates/refresh")
    assert client.post("/api/candidates/detect-all").status_code == 202
    client.app.state.tasks.wait(10)
    state = client.get("/api/tasks/current").json()
    assert state["running"] is False and state["error"] is None
    assert state["result"].startswith("Found job boards for")


def test_detect_endpoint_for_add_company(settings, tmp_path):
    client = client_for(settings, tmp_path)
    options = client.post("/api/detect", json={"name": "Docebo", "careers_url": "https://jobs.ashbyhq.com/docebo"}).json()
    assert options == [{"system": "ashby", "slug_or_url": "docebo", "how": "link", "confidence": "certain",
                        "note": "", "jobs_canada": None, "jobs_total": None}]


def test_enrich_all_and_one(settings, tmp_path):
    client = client_for(settings, tmp_path)
    conn = db.connect(tmp_path / "p4.db")
    shopify = db.upsert_company(conn, "Shopify", canadian=True)
    db.upsert_company(conn, "Hopper", canadian=True)
    conn.close()
    one = client.post("/api/enrich", json={"company_id": shopify}).json()
    assert "8,300" in one["result"]
    assert client.get(f"/api/companies/{shopify}").json()["size_source"] == "wikidata"

    assert client.post("/api/enrich", json={}).status_code == 202
    client.app.state.tasks.wait(10)
    assert "Looked up" in client.get("/api/tasks/current").json()["result"]


def test_accept_size_suggestion(settings, tmp_path):
    client = client_for(settings, tmp_path)
    conn = db.connect(tmp_path / "p4.db")
    company_id = db.upsert_company(conn, "Maybe Co")
    conn.execute("UPDATE companies SET size_suggestion = ? WHERE id = ?",
                 ('{"source": "wikidata", "employees": 420, "wikidata_id": "Q1"}', company_id))
    conn.commit()
    conn.close()
    company = client.get(f"/api/companies/{company_id}").json()
    assert company["size_suggestion"]["employees"] == 420
    accepted = client.post(f"/api/companies/{company_id}/accept-size").json()
    assert (accepted["employee_count"], accepted["size_suggestion"]) == (420, None)
    assert client.post(f"/api/companies/{company_id}/accept-size").status_code == 409


def test_one_task_at_a_time(settings, tmp_path):
    client = client_for(settings, tmp_path)
    client.app.state.tasks._state.running = True
    assert client.post("/api/enrich", json={}).status_code == 409
    assert client.post("/api/candidates/detect-all").status_code == 409
