"""Adding one job by its link: reading the page, matching the company, saving."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import FakeSources
from jobradar import cli, db, queries
from jobradar.dashboard import application_dashboard
from jobradar.http import HttpClient
from jobradar.manual import MANUAL, ManualJobError, clean_url, draft_from_html, existing_job, read_link, save_job
from jobradar.models import Location, RawJob
from jobradar.scan import load_boards
from jobradar.web import app as web_app

URL = "https://careers-acme.icims.com/jobs/12345/data-analyst/job?utm_source=linkedin"


def page(posting: dict | None, title="Data Analyst | Acme Careers") -> str:
    ld = f'<script type="application/ld+json">{json.dumps(posting)}</script>' if posting else ""
    return (f"<html><head><title>{title}</title><meta property='og:site_name' content='Acme'>{ld}</head>"
            "<body><h1>Job</h1></body></html>")


POSTING = {"@context": "https://schema.org", "@graph": [{"@type": "Organization", "name": "Acme"}, {
    "@type": "JobPosting",
    "title": "Data Analyst II",
    "hiringOrganization": {"@type": "Organization", "name": "Acme Financial"},
    "jobLocation": [{"@type": "Place", "address": {"addressLocality": "Toronto", "addressRegion": "Ontario",
                                                   "addressCountry": "CA"}}],
    "description": "&lt;p&gt;You have &lt;b&gt;3+ years&lt;/b&gt; of experience with SQL.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
    "datePosted": "2026-10-20T09:00:00-04:00",
    "employmentType": ["FULL_TIME"],
    "baseSalary": {"@type": "MonetaryAmount", "currency": "CAD",
                   "value": {"@type": "QuantitativeValue", "minValue": 80000, "maxValue": 95000, "unitText": "YEAR"}},
}]}


def test_reads_a_job_posting():
    d = draft_from_html(URL, page(POSTING))
    assert (d.title, d.company, d.city, d.province, d.country) == (
        "Data Analyst II", "Acme Financial", "Toronto", "ON", "CA")
    assert d.description == "You have 3+ years of experience with SQL.\n\n- Python"
    assert (d.posted_at, d.employment_type) == ("2026-10-20", "FULL_TIME")
    assert d.salary.startswith("CA$80,000") and d.salary.endswith("/ year")
    assert "title" in d.found and d.note == ""


def test_city_alone_gives_the_province_and_remote_is_read():
    posting = {"@type": "JobPosting", "title": "ML Engineer", "jobLocationType": "TELECOMMUTE",
               "jobLocation": {"address": {"addressLocality": "Vancouver"}}}
    d = draft_from_html(URL, page(posting))
    assert (d.city, d.province, d.country, d.remote) == ("Vancouver", "BC", "CA", True)


def test_outside_canada_has_no_province():
    posting = {"@type": "JobPosting", "title": "ML Engineer",
               "jobLocation": {"address": {"addressLocality": "Austin", "addressRegion": "TX", "addressCountry": "US"}}}
    d = draft_from_html(URL, page(posting))
    assert (d.province, d.country) == ("", "US")


def test_page_without_a_posting_falls_back_to_the_title():
    d = draft_from_html(URL, page(None, title="  Senior   Developer - Careers "))
    assert d.title == "Senior Developer - Careers" and d.company == "Acme"
    assert "fill in the details" in d.note


def test_clean_url():
    assert clean_url(URL) == "https://careers-acme.icims.com/jobs/12345/data-analyst/job"
    assert clean_url("https://Jobs.Example.com/a/?id=7&utm_medium=x#apply") == "https://jobs.example.com/a?id=7"
    with pytest.raises(ManualJobError):
        clean_url("not a link")


def _read(conn, settings, url, reply):
    import asyncio

    sources = FakeSources({("GET", url.split("?")[0]): reply})

    async def go():
        async with HttpClient(settings, transport=sources.transport()) as client:
            return await read_link(conn, client, url)
    return asyncio.run(go())


def test_read_link_matches_a_company_by_name(conn, settings):
    acme = db.upsert_company(conn, "acme financial", canadian=True)
    d = _read(conn, settings, URL, httpx.Response(200, text=page(POSTING)))
    assert (d.company_id, d.company) == (acme, "acme financial")


def test_read_link_matches_a_company_by_its_board(conn, settings):
    beta = db.upsert_company(conn, "Beta", canadian=True)
    db.upsert_board(conn, beta, "greenhouse", "betaco")
    url = "https://job-boards.greenhouse.io/betaco/jobs/999"
    d = _read(conn, settings, url, httpx.Response(200, text=page(None)))
    assert (d.company_id, d.company) == (beta, "Beta")


def test_unreadable_page_still_gives_a_draft(conn, settings):
    d = _read(conn, settings, URL, httpx.Response(500, text="oops"))
    assert d.title == "" and "couldn't be read" in d.note


def test_save_job(conn, tmp_path):
    job_id, new = save_job(conn, url=URL, title="Data Analyst II", company="Acme Financial", city="Toronto",
                           province="ON", description="3+ years of experience", status="applied")
    assert new
    row = conn.execute("SELECT j.*, b.system, b.enabled, c.name FROM jobs j JOIN boards b ON b.id = j.board_id "
                       "JOIN companies c ON c.id = b.company_id WHERE j.id = ?", (job_id,)).fetchone()
    assert (row["system"], row["enabled"], row["name"], row["status"]) == (MANUAL, 0, "Acme Financial", "applied")
    assert row["applied_at"] and row["url"] == URL
    assert load_boards(conn) == []  # never scanned
    # Listed like any Canadian job, and on the Applications page.
    assert [r["id"] for r in queries.search_jobs(conn, queries.JobFilter(provinces=["ON"], all_roles=True))[1]] == [job_id]
    assert application_dashboard(conn)["counts"]["applied"] == 1
    # The same link again (tracking parameters aside) is the same job.
    assert save_job(conn, url=URL.split("?")[0] + "/", title="x", company="y", province="ON") == (job_id, False)
    assert existing_job(conn, URL) == job_id


def test_save_remote_job_and_existing_company(conn):
    acme = db.upsert_company(conn, "Acme", canadian=True)
    job_id, _ = save_job(conn, url="https://x.example/job/1", title="Dev", company_id=acme, remote=True)
    rows = queries.search_jobs(conn, queries.JobFilter(provinces=["REMOTE"], all_roles=True))[1]
    assert [r["id"] for r in rows] == [job_id] and rows[0]["company"] == "Acme"


@pytest.mark.parametrize("fields, message", [
    ({"title": "", "company": "Acme", "province": "ON"}, "title"),
    ({"title": "Dev", "company": "Acme"}, "province"),
    ({"title": "Dev", "company": "Acme", "province": "ZZ"}, "Unknown province"),
    ({"title": "Dev", "province": "ON"}, "company"),
    ({"title": "Dev", "company": "Acme", "province": "ON", "status": "hired"}, "status"),
])
def test_save_job_explains_what_is_missing(conn, fields, message):
    with pytest.raises(ManualJobError, match=message):
        save_job(conn, url="https://x.example/job/2", **fields)


def test_api_add_job(conn, tmp_path, settings):
    company = db.upsert_company(conn, "Known", canadian=True)
    board = db.upsert_board(conn, company, "lever", "known")
    stored, _ = db.upsert_job(conn, board, RawJob("1", "Dev", "https://jobs.lever.co/known/1",
                                                  [Location("Toronto", "ON", "CA")]))
    sources = FakeSources({("GET", "https://careers-acme.icims.com/"): httpx.Response(200, text=page(POSTING))})
    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db", transport=sources.transport()))
    assert client.post("/api/jobs/from-link", json={"url": "https://jobs.lever.co/known/1/?lever-source=x"}).json() == {
        "existing": stored}
    draft = client.post("/api/jobs/from-link", json={"url": URL}).json()["draft"]
    assert draft["title"] == "Data Analyst II" and draft["province"] == "ON"
    bad = client.post("/api/jobs/manual", json={**draft, "province": "", "status": "applied"})
    assert bad.status_code == 400 and "province" in bad.json()["detail"]
    keys = ("url", "title", "company", "company_id", "city", "province", "remote", "description", "posted_at",
            "employment_type", "salary")
    made = client.post("/api/jobs/manual", json={**{k: draft[k] for k in keys}, "status": "applied"})
    assert made.status_code == 201 and made.json()["new"] is True
    job = client.get(f"/api/jobs/{made.json()['id']}").json()
    assert (job["system"], job["status"], job["level"], job["min_years"]) == ("manual", "applied", "mid", 3)
    assert client.post("/api/jobs/from-link", json={"url": "nope"}).status_code == 400


def test_cli_add_job_existing(tmp_path, capsys):
    db_path = tmp_path / "cli.db"
    conn = db.connect(db_path)
    save_job(conn, url="https://x.example/job/1", title="Dev", company="Acme", province="ON")
    conn.close()
    assert cli.main(["--root", str(tmp_path), "--db", str(db_path), "add-job", "https://x.example/job/1/"]) == 0
    assert "Already stored" in capsys.readouterr().out
