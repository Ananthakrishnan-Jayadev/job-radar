import asyncio
import json
import re
from datetime import UTC, date, datetime

import httpx
import pytest

from jobradar.connectors import CONNECTORS, FetchContext
from jobradar.connectors import workday
from jobradar.http import FetchError, HttpClient, NotFound
from jobradar.models import Board

from conftest import FIXTURES, FakeSources, Seq, fixture_json

TODAY = date(2026, 10, 26)


def board(system, slug, canadian=True):
    return Board(id=1, company_id=1, company_name="Test Co", company_canadian=canadian,
                 system=system, slug_or_url=slug)


def fetch(settings, sources, b, **ctx):
    async def go():
        async with HttpClient(settings, transport=sources.transport()) as client:
            context = FetchContext(settings=settings, today=TODAY, **ctx)
            return await CONNECTORS[b.system](b, client, context)
    return asyncio.run(go())


# --- Greenhouse --------------------------------------------------------------------

def test_greenhouse_fixture(settings):
    sources = FakeSources({("GET", "https://boards-api.greenhouse.io/v1/boards/faire/jobs"):
                           fixture_json("greenhouse_faire.json")})
    result = fetch(settings, sources, board("greenhouse", "faire", canadian=False))
    assert result.total == 72
    first = result.jobs[0]
    assert first.external_id == "8876236002"
    assert first.title == "Account Executive"
    assert first.posted_at == "2026-10-07"
    assert first.department == "Brand Partnerships"
    assert first.employment_type == "Regular"
    assert [(l.city, l.country) for l in first.locations] == [("New York", "US"), ("San Francisco", "US")]
    assert first.description and "<" not in first.description and "&lt;" not in first.description
    assert sources.requests[0].url.params["content"] == "true"


def test_greenhouse_canadian_offices_and_remote(settings):
    body = {"jobs": [
        {"id": 1, "title": " Data  Analyst ", "absolute_url": "u1", "location": {"name": "Toronto"},
         "offices": [{"name": "Toronto", "location": "Toronto, Ontario, Canada"}], "first_published": "2026-10-01T00:00:00-04:00"},
        {"id": 2, "title": "ML Engineer", "absolute_url": "u2", "location": {"name": "Remote - Canada"}, "offices": []},
    ], "meta": {"total": 2}}
    sources = FakeSources({("GET", "https://boards-api.greenhouse.io/"): body})
    jobs = fetch(settings, sources, board("greenhouse", "x")).jobs
    assert jobs[0].title == "Data Analyst"
    assert (jobs[0].locations[0].city, jobs[0].locations[0].province) == ("Toronto", "ON")
    assert jobs[1].locations[0].remote_canada_wide
    assert jobs[1].workplace == "remote"


# --- Lever -------------------------------------------------------------------------

def test_lever_fixture(settings):
    sources = FakeSources({("GET", "https://api.lever.co/v0/postings/wattpad"): fixture_json("lever_wattpad.json")})
    result = fetch(settings, sources, board("lever", "wattpad"))
    job = result.jobs[0]
    assert result.total == 2
    assert job.title == "[Wattpad] Engineering Manager"
    assert (job.locations[0].city, job.locations[0].province, job.locations[0].country) == ("Toronto", "ON", "CA")
    assert job.workplace == "hybrid"
    assert job.salary_text == "CA$140,000 – 180,000 / year"
    assert (job.salary_min, job.salary_max, job.currency) == (140000, 180000, "CAD")
    assert job.posted_at == datetime.fromtimestamp(1787156115902 / 1000, UTC).date().isoformat()
    assert job.employment_type == "Full-time"
    assert "What You'll Do" in job.description


def test_lever_country_fills_ambiguous_city(settings):
    body = [{"id": "a", "text": "Analyst", "hostedUrl": "u", "country": "CA",
             "categories": {"location": "London"}, "workplaceType": "onsite"}]
    sources = FakeSources({("GET", "https://api.lever.co/"): body})
    loc = fetch(settings, sources, board("lever", "x", canadian=False)).jobs[0].locations[0]
    assert (loc.city, loc.province, loc.country) == ("London", "ON", "CA")


# --- Ashby -------------------------------------------------------------------------

def test_ashby_fixture(settings):
    sources = FakeSources({("GET", "https://api.ashbyhq.com/"): fixture_json("ashby_wealthsimple.json")})
    jobs = fetch(settings, sources, board("ashby", "wealthsimple")).jobs
    office, remote = jobs
    assert (office.locations[0].city, office.locations[0].province) == ("Toronto", "ON")
    assert office.workplace == "onsite"
    assert office.salary_text == "CA$116K - CA$145K"
    assert (office.salary_min, office.salary_max, office.currency) == (116000, 145000, "CAD")
    assert office.posted_at == "2026-09-11"
    assert remote.locations[0].remote_canada_wide
    assert remote.workplace == "remote"
    assert sources.requests[0].url.params["includeCompensation"] == "true"


def test_ashby_skips_unlisted_and_reads_secondary_locations(settings):
    body = {"jobs": [
        {"id": "1", "title": "Hidden", "isListed": False, "location": "Toronto"},
        {"id": "2", "title": "Data Scientist", "isListed": True, "location": "Toronto",
         "secondaryLocations": [{"location": "Vancouver", "address": {"postalAddress": {
             "addressLocality": "Vancouver", "addressRegion": "BC", "addressCountry": "Canada"}}}]},
    ]}
    sources = FakeSources({("GET", "https://api.ashbyhq.com/"): body})
    result = fetch(settings, sources, board("ashby", "x"))
    assert [j.title for j in result.jobs] == ["Data Scientist"]
    assert [l.province for l in result.jobs[0].locations] == ["ON", "BC"]


# --- SmartRecruiters ---------------------------------------------------------------------

def sr_posting(i, released="2026-10-20T00:00:00Z", country="ca"):
    return {"id": str(i), "name": f"Job {i}", "releasedDate": released, "company": {"identifier": "Acme"},
            "location": {"city": "Toronto", "region": "ON", "country": country, "remote": False, "hybrid": True}}


def test_smartrecruiters_fixture(settings):
    body = fixture_json("smartrecruiters_canva.json")
    body["totalFound"] = len(body["content"])
    sources = FakeSources({("GET", "https://api.smartrecruiters.com/"): body})
    job = fetch(settings, sources, board("smartrecruiters", "canva", canadian=False)).jobs[0]
    assert job.title == "Strategic Customer Success Manager"
    assert (job.locations[0].city, job.locations[0].country) == ("Austin", "US")
    assert job.url == "https://jobs.smartrecruiters.com/Canva/6000000001518828"
    assert job.workplace == "hybrid"
    assert job.employment_type == "Full-time"


def test_smartrecruiters_pages_and_drops_old_postings(settings):
    page1 = {"totalFound": 150, "content": [sr_posting(i) for i in range(100)]}
    page2 = {"totalFound": 150, "content": [sr_posting(i) for i in range(100, 149)]
             + [sr_posting(999, released="2017-01-01T00:00:00Z")]}
    sources = FakeSources({("GET", "https://api.smartrecruiters.com/"): Seq([page1, page2])})
    result = fetch(settings, sources, board("smartrecruiters", "acme"))
    pages = [r for r in sources.requests if r.url.path.endswith("/postings")]
    assert len(pages) == 2
    assert pages[1].url.params["offset"] == "100"
    assert result.total == 150
    assert len(result.jobs) == 149
    assert "older than" in result.warnings[0]


# --- Workable, Recruitee, Breezy -----------------------------------------------------------

def test_workable_fixture(settings):
    sources = FakeSources({("GET", "https://apply.workable.com/"): fixture_json("workable_borrowell.json")})
    job = fetch(settings, sources, board("workable", "borrowell")).jobs[0]
    assert job.title == "Full Stack Developer"
    assert job.external_id == "E01BFED460"
    loc = job.locations[0]
    assert (loc.city, loc.province, loc.country, loc.remote) == ("Toronto", "ON", "CA", True)
    assert job.posted_at == "2026-05-08"
    assert job.workplace == "remote"


def test_recruitee_fixture(settings):
    sources = FakeSources({("GET", "https://bunq.recruitee.com/api/offers/"): fixture_json("recruitee_bunq.json")})
    job = fetch(settings, sources, board("recruitee", "bunq", canadian=False)).jobs[0]
    assert job.title == "Head of Product"
    assert job.locations[0].country == "NL"
    assert job.posted_at == "2026-10-15"
    assert job.salary_text is None
    assert job.description and "<p>" not in job.description


def test_recruitee_salary(settings):
    body = {"offers": [{"id": 5, "title": "Analyst", "status": "published", "careers_url": "u",
                        "city": "Toronto", "state_name": "Ontario", "country_code": "CA",
                        "salary": {"min": "80000", "max": "95000", "currency": "CAD", "period": "year"}}]}
    sources = FakeSources({("GET", "https://x.recruitee.com/"): body})
    job = fetch(settings, sources, board("recruitee", "x")).jobs[0]
    assert job.salary_text == "CA$80,000 – 95,000 / year"
    assert job.locations[0].province == "ON"


def test_breezy_fixture(settings):
    sources = FakeSources({("GET", "https://breezy.breezy.hr/json"): fixture_json("breezy_demo.json")})
    job = fetch(settings, sources, board("breezy", "breezy", canadian=False)).jobs[0]
    assert job.title == "Employee #12"
    assert (job.locations[0].city, job.locations[0].country) == ("Chaos", "US")
    assert job.salary_text == "$0.05 – $0.06 / hour"
    assert job.employment_type == "Other"


# --- Rippling ------------------------------------------------------------------------

def test_rippling_fixture_pages(settings):
    page0 = fixture_json("rippling_nesto.json")
    page1 = {"items": [{**page0["items"][0], "id": "other-id", "name": "Data Analyst"}],
             "page": 1, "totalPages": 2, "totalItems": 3}
    page0["totalItems"] = 3
    sources = FakeSources({("GET", "https://ats.rippling.com/"): Seq([page0, page1])})
    result = fetch(settings, sources, board("rippling", "nesto"))
    assert sources.requests[1].url.params["page"] == "1"
    assert [j.title for j in result.jobs] == ["Ingénieur IA Appliquée Senior", "Senior Applied AI Engineer", "Data Analyst"]
    assert result.jobs[0].locations[0].remote_canada_wide
    assert result.jobs[0].workplace == "remote"
    assert result.complete


def test_rippling_merges_one_entry_per_location(settings):
    entry = {"id": "j1", "name": "AI Delivery Manager", "url": "u", "department": {"name": "AI"}}
    page = {"page": 0, "totalPages": 1, "totalItems": 2, "items": [
        {**entry, "locations": [{"name": "Montreal, Canada (Remote)", "city": "Montreal", "countryCode": "CA",
                                  "workplaceType": "REMOTE"}]},
        {**entry, "locations": [{"name": "Toronto, Canada", "city": "Toronto", "countryCode": "CA",
                                  "workplaceType": "HYBRID"}]},
    ]}
    sources = FakeSources({("GET", "https://ats.rippling.com/"): page})
    result = fetch(settings, sources, board("rippling", "nesto"))
    assert len(result.jobs) == 1
    assert [l.province for l in result.jobs[0].locations] == ["QC", "ON"]
    assert result.jobs[0].workplace == "unknown"
    assert result.complete


def test_rippling_repeated_page_stops_and_is_partial(settings):
    page0 = fixture_json("rippling_nesto.json")  # says 2 pages, 39 items
    sources = FakeSources({("GET", "https://ats.rippling.com/"): page0})  # same page every time
    result = fetch(settings, sources, board("rippling", "nesto"))
    assert len(result.jobs) == 2
    assert not result.complete
    assert "repeated" in result.warnings[0]


# --- BambooHR ------------------------------------------------------------------------

def test_bamboohr_drops_test_postings(settings):
    sources = FakeSources({("GET", "https://waabi.bamboohr.com/"): fixture_json("bamboohr_waabi.json")})
    result = fetch(settings, sources, board("bamboohr", "waabi"))
    assert result.jobs == []
    assert result.total == 1


def test_bamboohr_job(settings):
    body = {"meta": {"totalCount": 1}, "result": [
        {"id": "7", "jobOpeningName": "Data Analyst", "departmentLabel": "Finance",
         "employmentStatusLabel": "Full-Time", "location": {"city": "Ottawa", "state": "Ontario"},
         "atsLocation": {"country": "Canada", "province": "Ontario", "city": "Ottawa"}, "isRemote": None}]}
    sources = FakeSources({("GET", "https://acme.bamboohr.com/"): body})
    job = fetch(settings, sources, board("bamboohr", "acme")).jobs[0]
    assert job.url == "https://acme.bamboohr.com/careers/7"
    assert (job.locations[0].city, job.locations[0].province) == ("Ottawa", "ON")


def test_bamboohr_redirect_means_not_found(settings):
    sources = FakeSources({("GET", "https://nobody.bamboohr.com/"):
                           httpx.Response(302, headers={"location": "https://www.bamboohr.com/"})})
    with pytest.raises(NotFound, match="board not found"):
        fetch(settings, sources, board("bamboohr", "nobody"))


# --- Workday -----------------------------------------------------------------------

WD = "https://sunlife.wd3.myworkdayjobs.com/Experienced-Jobs"
WD_API = "https://sunlife.wd3.myworkdayjobs.com/wday/cxs/sunlife/Experienced-Jobs"
CANADA_ID = "a30a87ed25634629aa6c3958aa2b91ea"


def workday_sources(canada_total=2, detail_ok=True):
    search = fixture_json("workday_sunlife_search.json")
    detail = fixture_json("workday_sunlife_detail.json")

    def jobs(request):
        body = __import__("json").loads(request.content)
        page = fixture_json("workday_sunlife_search.json")
        if body["appliedFacets"]:
            page["total"] = canada_total if body["offset"] == 0 else 0
            if body["offset"] >= 2:
                page["jobPostings"] = []
        return page

    sources = FakeSources({("POST", f"{WD_API}/jobs"): jobs})
    first_path = search["jobPostings"][0]["externalPath"]
    sources.add("GET", f"{WD_API}{first_path}", detail if detail_ok else httpx.Response(500))
    return sources


def test_workday_parse_site():
    assert workday.parse_site(WD) == ("sunlife.wd3.myworkdayjobs.com", "sunlife", "Experienced-Jobs")
    assert workday.parse_site("https://td.wd3.myworkdayjobs.com/en-US/TD_Bank_Careers/")[2] == "TD_Bank_Careers"
    with pytest.raises(FetchError):
        workday.parse_site("https://example.com/careers")


def test_workday_find_country_facet_nested():
    facets = [{"facetParameter": "locationMainGroup", "values": [
        {"facetParameter": "locationCountry", "descriptor": "Countries",
         "values": [{"descriptor": "United States", "id": "us1"}, {"descriptor": "Canada", "id": "ca1"}]}]}]
    assert workday.find_country_facet(facets) == ("locationCountry", "ca1")
    assert workday.find_country_facet(fixture_json("workday_sunlife_search.json")["facets"]) == \
        ("Location_Country", CANADA_ID)
    assert workday.find_country_facet([]) is None


def test_workday_lists_canada_and_fetches_details(settings):
    sources = workday_sources()
    result = fetch(settings, sources, board("workday", WD))
    bodies = sources.bodies()
    assert bodies[0]["appliedFacets"] == {}
    assert bodies[1]["appliedFacets"] == {"Location_Country": [CANADA_ID]}
    assert all(b["limit"] == 20 for b in bodies)
    assert result.total == 6
    assert result.complete

    detailed, summary = result.jobs
    assert detailed.external_id == "Data-Scientist_JR00128241"
    assert detailed.details_fetched
    assert [(l.city, l.province) for l in detailed.locations] == [("Toronto", "ON"), ("Waterloo", "ON")]
    assert detailed.posted_at == "2026-10-23"
    assert detailed.employment_type == "Full time"
    assert detailed.description

    # The second job's detail isn't in the table (404): kept from the list.
    assert not summary.details_fetched
    assert (summary.locations[0].city, summary.locations[0].province) == ("Toronto", "ON")
    assert summary.posted_at == "2026-10-22"  # "Posted 4 Days Ago"
    assert summary.url == f"{WD}/job/Toronto-Ontario/Senior-Data-Scientist_JR00125593"
    assert any("detail for Senior-Data-Scientist" in w for w in result.warnings)


def test_workday_skips_known_details_and_respects_cap(settings):
    sources = workday_sources()
    result = fetch(settings, sources, board("workday", WD), known_ids={"Data-Scientist_JR00128241"})
    assert not [r for r in sources.requests
                if r.method == "GET" and str(r.url).endswith("/Data-Scientist_JR00128241")]
    assert not result.jobs[0].details_fetched

    settings.workday.max_details_per_scan = 0
    sources = workday_sources()
    fetch(settings, sources, board("workday", WD))
    assert not [r for r in sources.requests if r.method == "GET"]


def test_workday_over_limit_searches_terms(settings):
    settings.workday.max_list = 1
    sources = workday_sources(canada_total=500)
    result = fetch(settings, sources, board("workday", WD), search_terms=["data scientist", "analyst"])
    searched = [b["searchText"] for b in sources.bodies() if b["searchText"]]
    assert searched == ["data scientist", "analyst"]
    assert not result.complete
    assert "over the 1 limit" in result.warnings[0]
    assert len(result.jobs) == 1  # each search capped at 1; both found the same posting


def test_workday_no_canada_facet(settings):
    body = {"total": 10, "jobPostings": [], "facets": []}
    sources = FakeSources({("POST", f"{WD_API}/jobs"): body})
    result = fetch(settings, sources, board("workday", WD))
    assert result.jobs == [] and result.total == 10
    assert "no Canadian locations" in result.warnings[0]


def test_workday_wrong_site_name(settings):
    sources = FakeSources({("POST", f"{WD_API}/jobs"): httpx.Response(422)})
    with pytest.raises(NotFound, match="site name"):
        fetch(settings, sources, board("workday", WD))


# --- SAP SuccessFactors ---------------------------------------------------------------

SF = "https://jobs.scotiabank.com"


def sf_sources(text=None):
    body = text if text is not None else (FIXTURES / "successfactors_scotiabank.xml").read_text()
    return FakeSources({("GET", f"{SF}/sitemap.xml"): httpx.Response(200, text=body)})


def test_successfactors_fixture(settings):
    result = fetch(settings, sf_sources(), board("successfactors", SF))
    assert result.total == 5
    by_place = {j.locations[0].raw: j for j in result.jobs}
    ajax = by_place["Ajax, ON, CA"]
    assert (ajax.locations[0].city, ajax.locations[0].province, ajax.locations[0].country) == ("Ajax", "ON", "CA")
    assert "(" not in ajax.title  # the "(Ajax, ON, CA)" suffix is removed
    assert ajax.url.startswith("https://jobs.scotiabank.com/job/")
    assert ajax.department
    assert ajax.description and "<p>" not in ajax.description and "base64" not in ajax.description
    assert by_place["New York City, NY, US"].locations[0].country == "US"
    assert by_place["Bogota, DC, CO"].locations[0].country == "CO"
    software = [j for j in result.jobs if "Software" in j.title]
    assert software and software[0].locations[0].province == "ON"


def test_successfactors_bad_feed(settings):
    with pytest.raises(FetchError, match="isn't valid XML"):
        fetch(settings, sf_sources("<html>not a feed"), board("successfactors", SF))
    with pytest.raises(FetchError, match="isn't a SuccessFactors job feed"):
        fetch(settings, sf_sources("<html><body>maintenance</body></html>"), board("successfactors", SF))


def test_successfactors_drops_embedded_images_before_parsing(settings):
    text = (FIXTURES / "successfactors_scotiabank.xml").read_text()
    huge = text.replace("data:image/png;base64,TRIMMED", "data:image/png;base64," + "A" * 200_000)
    result = fetch(settings, sf_sources(huge), board("successfactors", SF))
    assert all("AAAA" not in (j.description or "") for j in result.jobs)


# --- JazzHR -----------------------------------------------------------------------

def jazz_sources(slug, fixture):
    return FakeSources({("GET", f"https://app.jazz.co/feeds/export/jobs/{slug}"):
                        httpx.Response(200, text=(FIXTURES / fixture).read_text())})


def test_jazzhr_remote_in_city_field(settings):
    result = fetch(settings, jazz_sources("xello", "jazzhr_xello.xml"), board("jazzhr", "xello"))
    assert result.total == 3
    by_title = {j.title: j for j in result.jobs}
    sales = by_title["Sales Manager"].locations[0]
    # "Remote – Canada & United States" in the city field: remote, no city.
    assert (sales.city, sales.province, sales.country, sales.remote) == (None, "ON", "CA", True)
    engineer = by_title["Principal Software Engineer"]
    assert (engineer.locations[0].city, engineer.locations[0].remote) == ("Toronto", True)
    assert engineer.workplace == "remote"
    assert engineer.url.startswith("https://xello.applytojob.com/apply/")
    assert engineer.department == "Engineering"
    assert re.match(r"\d{4}-\d{2}-\d{2}$", engineer.posted_at)  # from the id
    assert engineer.description and "<" not in engineer.description


def test_jazzhr_locations(settings):
    result = fetch(settings, jazz_sources("apertera", "jazzhr_apertera.xml"), board("jazzhr", "apertera"))
    places = {(j.locations[0].city, j.locations[0].province, j.locations[0].country) for j in result.jobs}
    assert places == {(None, None, "CA"), (None, None, "ES"), ("Montreal", "QC", "CA"), ("Toronto", "ON", "CA")}


def test_jazzhr_unknown_company(settings):
    with pytest.raises(NotFound):
        fetch(settings, FakeSources(), board("jazzhr", "nobody"))


# --- Pinpoint, Teamtailor, Humi ----------------------------------------------------------

def place(job):
    loc = job.locations[0]
    return (loc.city, loc.province, loc.country, loc.remote)


def test_pinpoint_fixture(settings):
    sources = FakeSources({("GET", "https://crawfordtech.pinpointhq.com/postings.json"): fixture_json("pinpoint_postings.json")})
    result = fetch(settings, sources, board("pinpoint", "crawfordtech"))
    assert result.total == 8
    jobs = {j.title: j for j in result.jobs}
    support = next(j for t, j in jobs.items() if t.startswith("Applications Support Manager"))
    assert support.salary_text == "US$85,000 – 140,000 / year" and support.currency == "USD"
    assert support.workplace == "remote" and place(support)[2] == "US"  # "Remote U.S."
    assert support.description and "<" not in support.description
    canadian = {place(j) for j in result.jobs if j.locations[0].in_canada}
    assert ("Toronto", "ON", "CA", False) in canadian  # "Greater Toronto Area, Canada"
    assert ("Calgary", "AB", "CA", False) in canadian
    assert ("Shawinigan", "QC", "CA", False) in canadian
    assert any(p[:3] == (None, None, "CA") and p[3] for p in canadian)  # "Remote, Canada"
    assert not any(j.locations[0].in_canada for j in result.jobs if "Cardiff" in j.locations[0].raw)
    assert all(j.department for j in result.jobs)


def test_teamtailor_fixture(settings):
    site = "https://commonsku.na.teamtailor.com"
    sources = FakeSources({("GET", f"{site}/jobs.rss"): httpx.Response(
        200, text=(FIXTURES / "teamtailor_commonsku.rss").read_text())})
    result = fetch(settings, sources, board("teamtailor", site))
    assert result.total == 6
    data = next(j for j in result.jobs if j.title == "Staff Data Engineer")
    assert data.url.startswith(f"{site}/jobs/")
    assert data.workplace == "remote"
    assert re.match(r"\d{4}-\d{2}-\d{2}$", data.posted_at)
    assert (data.locations[0].city, data.locations[0].province, data.locations[0].country) == ("Toronto", "ON", "CA")
    assert data.department
    manager = next(j for j in result.jobs if j.title == "Engineering Manager, Data")
    assert manager.posted_at == "2026-10-20"


def test_humi_fixture(settings):
    sources = FakeSources({("GET", "https://hypercare.applytojobs.ca/"): httpx.Response(
        200, text=(FIXTURES / "humi_hypercare.html").read_text())})
    result = fetch(settings, sources, board("humi", "hypercare"))
    jobs = {j.title: j for j in result.jobs}
    assert set(jobs) == {"Future Internship Opportunities - Marketing, Business Operations, Customer Success",
                         "Future Opportunities - Engineering Team"}
    intern = jobs["Future Internship Opportunities - Marketing, Business Operations, Customer Success"]
    assert intern.url == "https://hypercare.applytojobs.ca/internships/18555"
    assert intern.external_id == "18555"
    assert (intern.workplace, intern.employment_type, intern.posted_at) == ("remote", "internship", "2022-12-22")
    assert place(intern) == ("Toronto", "ON", "CA", True)
    assert jobs["Future Opportunities - Engineering Team"].workplace == "unknown"  # no badge


def test_humi_single_job_with_hybrid_badge(settings):
    sources = FakeSources({("GET", "https://ecopiatech.applytojobs.ca/"): httpx.Response(
        200, text=(FIXTURES / "humi_ecopia.html").read_text())})
    job = fetch(settings, sources, board("humi", "ecopiatech")).jobs[0]
    assert (job.workplace, job.posted_at, place(job)[:3]) == ("hybrid", "2026-09-09", ("Toronto", "ON", "CA"))


def test_humi_page_changed(settings):
    sources = FakeSources({("GET", "https://acme.applytojobs.ca/"): httpx.Response(200, text="<html>nothing</html>")})
    with pytest.raises(FetchError, match="doesn't look like a Humi"):
        fetch(settings, sources, board("humi", "acme"))



# Facets shaped like real sites without a country filter (PwC, iA, Capital One).
LOCATION_FACETS = [
    {"facetParameter": "timeType", "values": [{"descriptor": "Full time", "id": "ft", "count": 9}]},
    {"facetParameter": "locationMainGroup", "values": [
        {"facetParameter": "locations", "descriptor": "Locations", "values": [
            {"descriptor": "Toronto", "id": "tor", "count": 5},
            {"descriptor": "Calgary, Alberta", "id": "cal", "count": 2},
            {"descriptor": "AB - Campinas", "id": "camp", "count": 1},
            {"descriptor": "New York, NY", "id": "nyc", "count": 7},
            {"descriptor": "London", "id": "lon", "count": 3},
        ]}]},
]


def test_workday_find_canada_locations():
    assert workday.find_canada_locations(LOCATION_FACETS) == ("locations", ["tor", "cal"])
    assert workday.find_canada_locations([]) is None


def test_workday_falls_back_to_location_filter(settings):
    def jobs(request):
        body = json.loads(request.content)
        if not body["appliedFacets"]:
            return {"total": 18, "jobPostings": [], "facets": LOCATION_FACETS}
        assert body["appliedFacets"] == {"locations": ["tor", "cal"]}
        return {"total": 2, "jobPostings": [
            {"title": "Data Analyst", "externalPath": "/job/Toronto/Data-Analyst_R1", "locationsText": "Toronto"},
            # Listed under New York, but the filter says it's also open in Canada.
            {"title": "AI Engineer", "externalPath": "/job/New-York-NY/AI-Engineer_R2", "locationsText": "3 Locations"},
        ]}

    sources = FakeSources({("POST", f"{WD_API}/jobs"): jobs})
    settings.workday.max_details_per_scan = 0
    result = fetch(settings, sources, board("workday", WD, canadian=False))
    assert "filtered by 2 Canadian locations" in result.warnings[0]
    analyst, engineer = result.jobs
    assert (analyst.locations[0].city, analyst.locations[0].province) == ("Toronto", "ON")
    assert engineer.locations[0].country == "US"
    assert engineer.locations[-1].in_canada  # placeholder until the detail page is read


def test_successfactors_search_pages_when_no_feed(settings):
    site = "https://careers.ey.com"
    urlset = '<?xml version="1.0"?><urlset xmlns="http://www.google.com/schemas/sitemap/0.9"><url><loc>x</loc></url></urlset>'
    page = (FIXTURES / "successfactors_search_ey.html").read_text()
    sources = FakeSources({
        ("GET", f"{site}/sitemap.xml"): httpx.Response(200, text=urlset),
        ("GET", f"{site}/search/"): httpx.Response(200, text=page),
    })
    result = fetch(settings, sources, board("successfactors", site))
    assert result.total == 423
    search = [r for r in sources.requests if "/search/" in str(r.url)]
    assert search[0].url.params["locationsearch"] == "Canada"
    assert search[1].url.params["startrow"] == "25"
    job = result.jobs[0]
    assert job.external_id == "1449196533"
    assert job.title == "International Tax Advisory Services - Montréal - Senior Tax Staff"
    assert job.url.startswith("https://careers.ey.com/ey/job/")
    assert (job.locations[0].city, job.locations[0].province, job.locations[0].country) == ("Montréal", "QC", "CA")
    # The fixture repeats the same 3 rows on every page: stops instead of looping forever.
    assert len(result.jobs) == 3 and not result.complete


def test_successfactors_script_only_site(settings):
    site = "https://jobs.teck.com"
    urlset = '<?xml version="1.0"?><urlset xmlns="http://www.google.com/schemas/sitemap/0.9"></urlset>'
    sources = FakeSources({
        ("GET", f"{site}/sitemap.xml"): httpx.Response(200, text=urlset),
        ("GET", f"{site}/search/"): httpx.Response(200, text="<html><body>loading…</body></html>"),
    })
    with pytest.raises(FetchError, match="by script"):
        fetch(settings, sources, board("successfactors", site))


# --- Job descriptions from detail pages (wanted roles only) ------------------------------

def only_engineers(title):
    return "engineer" in title.lower() or "developer" in title.lower()


def test_smartrecruiters_detail_description(settings):
    post = sr_posting(1)
    post["id"], post["name"] = "744000138709868", "Software Engineering Developer"
    other = {**sr_posting(2), "name": "Payroll Clerk"}
    api = "https://api.smartrecruiters.com/v1/companies/acme/postings"
    sources = FakeSources({("GET", api): {"totalFound": 2, "content": [post, other]},
                           ("GET", f"{api}/744000138709868"): fixture_json("smartrecruiters_detail.json")})
    jobs = fetch(settings, sources, board("smartrecruiters", "acme"), wants=only_engineers).jobs
    assert "Air & Naval (A&N) Sonar division" in jobs[0].description
    assert "Company Description" not in jobs[0].description and "<p>" not in jobs[0].description
    assert jobs[1].description is None  # not a wanted role: no detail request
    assert [r.url.path.rsplit("/", 1)[-1] for r in sources.requests] == ["postings", "744000138709868"]


def test_details_only_for_jobs_in_canada(settings):
    api = "https://api.smartrecruiters.com/v1/companies/acme/postings"
    page = {"totalFound": 2, "content": [{**sr_posting(1), "name": "Developer"},
                                         {**sr_posting(2, country="us"), "name": "Developer"}]}
    sources = FakeSources({("GET", api): page, ("GET", f"{api}/"): {"jobAd": {"sections": {}}}})
    fetch(settings, sources, board("smartrecruiters", "acme", canadian=False))
    assert [r.url.path.rsplit("/", 1)[-1] for r in sources.requests] == ["postings", "1"]


def test_details_skip_known_jobs_and_respect_the_cap(settings):
    settings.details_per_board = 2
    page = {"totalFound": 4, "content": [{**sr_posting(i), "name": f"Developer {i}"} for i in range(4)]}
    api = "https://api.smartrecruiters.com/v1/companies/acme/postings"
    sources = FakeSources({("GET", api): page, ("GET", f"{api}/"): {"jobAd": {"sections": {
        "jobDescription": {"text": "<p>Build things.</p>"}}}}})
    result = fetch(settings, sources, board("smartrecruiters", "acme"), known_ids={"0"})
    assert [j.description for j in result.jobs] == [None, "Build things.", "Build things.", None]
    assert "1 job descriptions left for the next scan" in result.warnings


def test_detail_failure_does_not_fail_the_board(settings):
    api = "https://api.smartrecruiters.com/v1/companies/acme/postings"
    sources = FakeSources({("GET", api): {"totalFound": 1, "content": [sr_posting(1)]},
                           ("GET", f"{api}/1"): httpx.Response(500)})
    result = fetch(settings, sources, board("smartrecruiters", "acme"))
    assert len(result.jobs) == 1 and result.jobs[0].description is None
    assert "detail for 1 failed" in result.warnings[0]


def test_workable_descriptions_in_one_request(settings):
    sources = FakeSources({("GET", "https://apply.workable.com/"): fixture_json("workable_borrowell_details.json")})
    job = fetch(settings, sources, board("workable", "borrowell")).jobs[0]
    assert sources.requests[0].url.params["details"] == "true"
    assert len(sources.requests) == 1
    assert job.description.startswith("About Borrowell:\n")


def test_rippling_detail_description(settings):
    page = {"page": 0, "totalPages": 1, "totalItems": 1, "items": [
        {"id": "6f66c7ed-7735-406f-b936-ef6018ed5071", "name": "Data & AI Product Analyst", "url": "u",
         "locations": [{"name": "Montreal, Canada", "city": "Montreal", "countryCode": "CA"}]}]}
    api = "https://ats.rippling.com/api/v2/board/axya-inc/jobs"
    sources = FakeSources({("GET", api): page,
                           ("GET", f"{api}/6f66c7ed"): fixture_json("rippling_detail.json")})
    job = fetch(settings, sources, board("rippling", "axya-inc")).jobs[0]
    assert job.posted_at == "2026-08-26"
    assert "About Axya" in job.description and "style=" not in job.description


def test_bamboohr_detail_description(settings):
    body = {"meta": {"totalCount": 1}, "result": [
        {"id": "52", "jobOpeningName": "Junior AI Developer", "location": {"city": "Ottawa", "state": "Ontario"},
         "atsLocation": {"country": "Canada", "province": "Ontario", "city": "Ottawa"}}]}
    sources = FakeSources({("GET", "https://arcadion.bamboohr.com/careers/list"): body,
                           ("GET", "https://arcadion.bamboohr.com/careers/52/detail"):
                               fixture_json("bamboohr_detail.json")})
    job = fetch(settings, sources, board("bamboohr", "arcadion")).jobs[0]
    assert job.description.startswith("📍 About Arcadion\n")
    assert job.posted_at == "2025-05-01"
    assert job.salary_text is None


def test_successfactors_description_from_job_page():
    from jobradar.connectors.successfactors import description_from_page

    text = description_from_page((FIXTURES / "successfactors_job_ey.html").read_text())
    assert text.startswith("At EY, you’ll have the chance to build a career")
    assert "Apply now" not in text and "Finance Transformation" not in text
    assert description_from_page("<html><body>nothing here</body></html>") is None


def test_successfactors_search_mode_fetches_wanted_descriptions(settings):
    site = "https://careers.ey.com"
    urlset = '<?xml version="1.0"?><urlset xmlns="http://www.google.com/schemas/sitemap/0.9"></urlset>'
    sources = FakeSources({
        ("GET", f"{site}/sitemap.xml"): httpx.Response(200, text=urlset),
        ("GET", f"{site}/search/"): httpx.Response(200, text=(FIXTURES / "successfactors_search_ey.html").read_text()),
        ("GET", f"{site}/ey/job/"): httpx.Response(200, text=(FIXTURES / "successfactors_job_ey.html").read_text()),
    })
    result = fetch(settings, sources, board("successfactors", site), wants=lambda t: "Tax" in t)
    wanted = [j for j in result.jobs if "Tax" in j.title]
    assert wanted and all(j.description.startswith("At EY") for j in wanted)
    assert all(j.description is None for j in result.jobs if "Tax" not in j.title)


def test_workday_details_for_wanted_roles_only(settings):
    sources = workday_sources()
    result = fetch(settings, sources, board("workday", WD), wants=lambda t: False)
    assert not any("/job/" in str(r.url) for r in sources.requests if r.method == "GET")
    assert not any(j.details_fetched for j in result.jobs)
    assert not any("left for the next scan" in w for w in result.warnings)


# --- HiBob ---------------------------------------------------------------------------

def test_hibob_fixture(settings):
    sources = FakeSources({("GET", "https://xanadu.careers.hibob.com/api/job-ad"): fixture_json("hibob_xanadu.json")})
    result = fetch(settings, sources, board("hibob", "xanadu"))
    assert sources.requests[0].headers["Referer"] == "https://xanadu.careers.hibob.com/jobs"
    assert result.total == 4
    remote, toronto, us, data = result.jobs
    assert remote.title == "Principal Analog ASIC Design Engineer"
    assert remote.url == "https://xanadu.careers.hibob.com/jobs/ce50ce64-bce7-40e5-8b07-362045e73ad1"
    assert remote.locations[0].remote_canada_wide and remote.workplace == "remote"
    assert remote.posted_at == "2026-08-24"
    assert remote.description.startswith("About Xanadu:") and "<strong>" not in remote.description
    assert (toronto.locations[0].city, toronto.locations[0].province) == ("Toronto", "ON")
    assert toronto.workplace in ("hybrid", "onsite")
    assert us.locations[0].country == "US" and us.locations[0].city is None
    assert data.title == "Senior Data Scientist – Decision Intelligence"
    assert data.department and data.employment_type == "Full Time"


def test_hibob_salary(settings):
    item = {"id": "x1", "title": "ML Engineer", "site": "Toronto", "country": "Canada", "workspaceType": "On site",
            "payTransparencyMinSalary": 130000, "payTransparencyMaxSalary": 150000,
            "payTransparencySalaryCurrency": "CAD", "payTransparencySalaryPayPeriod": "Annual"}
    sources = FakeSources({("GET", "https://acme.careers.hibob.com/"): {"jobAdDetails": [item]}})
    job = fetch(settings, sources, board("hibob", "acme")).jobs[0]
    assert job.salary_text == "CA$130,000 – 150,000 / year"
    assert job.workplace == "onsite"
