"""Phase 4: company sizes, job-system detection, stillhiring candidates."""

import asyncio

import httpx
import pytest

from jobradar import candidates, db, detect, enrich
from jobradar.http import HttpClient
from jobradar.sources import stillhiring

from conftest import FIXTURES, FakeSources, fixture_json

WIKI = "https://www.wikidata.org/w/api.php"


def wikidata_reply():
    data = fixture_json("wikidata_api.json")

    def reply(request: httpx.Request):
        params = request.url.params
        if params["action"] == "wbsearchentities":
            return data["search"].get(params["search"], {"search": []})
        ids = params["ids"].split("|")
        return {"entities": {i: data["entities"]["entities"][i] for i in ids if i in data["entities"]["entities"]}}

    return reply


def company(conn, name, canadian=True, **fields):
    company_id = db.upsert_company(conn, name, canadian=canadian)
    for key, value in fields.items():
        conn.execute(f"UPDATE companies SET {key} = ? WHERE id = ?", (value, company_id))
    conn.commit()
    return company_id


def size(conn, company_id):
    row = conn.execute("SELECT employee_count, size_source FROM companies WHERE id = ?", (company_id,)).fetchone()
    return row["employee_count"], row["size_source"]


# --- size precedence --------------------------------------------------------------

def test_size_precedence(conn):
    c = company(conn, "Acme")
    assert enrich.apply_size(conn, c, 40, "estimate")
    assert enrich.apply_size(conn, c, 120, "wikidata")
    assert not enrich.apply_size(conn, c, 60, "estimate")  # worse source
    assert enrich.apply_size(conn, c, 150, "stillhiring")
    assert enrich.apply_size(conn, c, 160, "stillhiring")  # same source refreshes
    conn.execute("UPDATE companies SET employee_count = 99, size_source = 'manual' WHERE id = ?", (c,))
    assert not enrich.apply_size(conn, c, 170, "stillhiring")  # manual always wins
    assert size(conn, c) == (99, "manual")
    assert not enrich.apply_size(conn, c, None, "stillhiring")


@pytest.mark.parametrize("total,systems,expected", [
    (None, [], None), (0, ["ashby"], None), (3, ["ashby"], 10), (8, ["lever"], 50), (40, ["ashby"], 200),
    (150, ["greenhouse"], 1000), (700, ["greenhouse"], 5000), (20, ["workday"], 1000), (900, ["workday"], 5000),
])
def test_estimate_size(total, systems, expected):
    assert enrich.estimate_size(total, systems) == expected


def test_estimate_missing_only_fills_gaps(conn):
    a = company(conn, "Small", employee_count=None)
    b = company(conn, "Known", employee_count=300, size_source="wikidata")
    db.upsert_board(conn, a, "ashby", "small")
    db.upsert_board(conn, b, "ashby", "known")
    conn.execute("UPDATE boards SET total_open = 30")
    conn.commit()
    assert enrich.estimate_missing(conn) == 1
    assert size(conn, a) == (200, "estimate")
    assert size(conn, b) == (300, "wikidata")


# --- Wikidata ---------------------------------------------------------------------

def test_latest_employees_prefers_newest_date():
    entities = fixture_json("wikidata_api.json")["entities"]["entities"]
    assert enrich.latest_employees(entities["Q7501150"]) == (8300, "2023")
    assert enrich.latest_employees(entities["Q1194832"]) is None  # TD has no count on Wikidata


def test_pick_match():
    data = fixture_json("wikidata_api.json")
    entities = data["entities"]["entities"]
    match, certain = enrich.pick_match("Shopify", True, data["search"]["Shopify"]["search"], entities)
    assert (match.wikidata_id, match.employees, match.in_canada, certain) == ("Q7501150", 8300, True, True)
    # Hopper: a surname, a game, a GPU: no company with a head count.
    assert enrich.pick_match("Hopper", True, data["search"]["Hopper"]["search"], entities) == (None, False)
    # TD Bank: companies found, none with a head count.
    assert enrich.pick_match("TD Bank", True, data["search"]["TD Bank"]["search"], entities) == (None, False)


def test_pick_match_uncertain_becomes_suggestion():
    data = fixture_json("wikidata_api.json")
    entities = data["entities"]["entities"]
    match, certain = enrich.pick_match("Shopify Inc. Canada", True, data["search"]["Shopify"]["search"], entities)
    assert match.wikidata_id == "Q7501150" and not certain  # name doesn't match exactly


def test_enrich_end_to_end(conn, settings):
    shopify = company(conn, "Shopify")
    hopper = company(conn, "Hopper")
    td = company(conn, "TD Bank")
    db.upsert_board(conn, td, "workday", "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers")
    conn.execute("UPDATE boards SET total_open = 1600")
    conn.commit()
    sources = FakeSources({("GET", WIKI): wikidata_reply()})
    summary = enrich.run_enrich(conn, settings, transport=sources.transport())
    assert summary.looked_up == 3 and summary.from_wikidata == 1 and summary.estimated == 1
    assert size(conn, shopify) == (8300, "wikidata")
    assert conn.execute("SELECT wikidata_id FROM companies WHERE id = ?", (shopify,)).fetchone()[0] == "Q7501150"
    assert size(conn, hopper) == (None, None)
    assert size(conn, td) == (5000, "estimate")
    # Entities are fetched in one batch, not one request per company.
    assert sum(1 for r in sources.requests if r.url.params["action"] == "wbgetentities") == 1


def test_suggestion_accept(conn):
    c = company(conn, "Maybe Co")
    enrich.suggest_size(conn, c, {"source": "wikidata", "employees": 420, "wikidata_id": "Q1"})
    assert enrich.accept_suggestion(conn, c)
    assert size(conn, c) == (420, "wikidata")
    assert conn.execute("SELECT size_suggestion FROM companies WHERE id = ?", (c,)).fetchone()[0] is None


# --- detection ----------------------------------------------------------------------

@pytest.mark.parametrize("url,system,slug", [
    ("https://jobs.ashbyhq.com/docebo", "ashby", "docebo"),
    ("https://jobs.lever.co/cority", "lever", "cority"),
    ("https://job-boards.greenhouse.io/stackadapt", "greenhouse", "stackadapt"),
    ("https://job-boards.greenhouse.io/embed/job_board?for=hootsuite", "greenhouse", "hootsuite"),
    ("https://boards.greenhouse.io/embed/job_board/js?for=faire", "greenhouse", "faire"),
    ("https://bb.wd3.myworkdayjobs.com/BlackBerry", "workday", "https://bb.wd3.myworkdayjobs.com/BlackBerry"),
    ("https://bb.wd3.myworkdayjobs.com/en-US/BlackBerry/job/x", "workday", "https://bb.wd3.myworkdayjobs.com/BlackBerry"),
    ("https://avidbots.bamboohr.com/careers", "bamboohr", "avidbots"),
    ("https://petalmd.recruitee.com/", "recruitee", "petalmd"),
    ("https://ats.rippling.com/paper-careers/jobs", "rippling", "paper-careers"),
    ("https://apply.workable.com/borrowell/", "workable", "borrowell"),
    ("https://careers.smartrecruiters.com/Canva", "smartrecruiters", "Canva"),
    ("https://acme.breezy.hr/p/123", "breezy", "acme"),
    ("https://xello.applytojob.com/", "jazzhr", "xello"),
    ("https://apertera.applytojob.com/apply", "jazzhr", "apertera"),
])
def test_from_url(url, system, slug):
    found = detect.from_url(url)
    assert (found.system, found.slug_or_url, found.confidence) == (system, slug, "certain")


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/company/1password/jobs/", "https://www.shopify.com/careers", None, "",
    "https://jobs.gem.com/biorender",
])
def test_from_url_none(url):
    assert detect.from_url(url) is None


def test_from_html_embedded_boards():
    html = """<html><a href="https://www.example.com/about">About</a>
      <iframe src="https://job-boards.greenhouse.io/embed/job_board?for=acme&b=1"></iframe>
      <script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>
      <a href="https://jobs.lever.co/acme-corp/123">Apply</a></html>"""
    found = detect.from_text(html, "page")
    assert [(d.system, d.slug_or_url, d.confidence) for d in found] == [
        ("greenhouse", "acme", "likely"), ("lever", "acme-corp", "likely")]


@pytest.mark.parametrize("name,guesses", [
    ("Top Hat", ["tophat", "top-hat"]),
    ("Avidbots Corp.", ["avidbots"]),
    ("1Password", ["1password"]),
    ("Dye & Durham Corporation", ["dyedurham", "dye-durham"]),
    ("Block 64", ["block64", "block-64"]),  # never just "block": that's Block Inc.
])
def test_slug_guesses(name, guesses):
    assert detect.slug_guesses(name) == guesses


def detect_company(settings, sources, name, url, canadian=True, guess=True):
    async def go():
        async with HttpClient(settings, transport=sources.transport()) as client:
            return await detect.detect_company(client, settings, name, url, canadian, guess=guess)
    return asyncio.run(go())


def test_detect_from_careers_page(settings):
    sources = FakeSources({("GET", "https://acme.example/careers"): httpx.Response(
        200, text='<a href="https://jobs.ashbyhq.com/acme">Open roles</a>')})
    found = detect_company(settings, sources, "Acme", "https://acme.example/careers")
    assert [(d.system, d.slug_or_url, d.how) for d in found] == [("ashby", "acme", "page")]
    assert "linked from" in found[0].note


def test_detect_follows_jobs_link_one_page(settings):
    sources = FakeSources({
        ("GET", "https://acme.example/careers"): httpx.Response(200, text='<a href="/careers/openings">See jobs</a>'),
        ("GET", "https://acme.example/careers/openings"): httpx.Response(
            200, text='<script src="https://boards.greenhouse.io/embed/job_board/js?for=acmeinc"></script>'),
    })
    found = detect_company(settings, sources, "Acme", "https://acme.example/careers")
    assert [(d.system, d.slug_or_url) for d in found] == [("greenhouse", "acmeinc")]


def test_detect_guess_keeps_only_boards_with_canadian_jobs(settings):
    canadian = {"jobs": [{"id": "1", "title": "Analyst", "isListed": True, "location": "Toronto",
                          "address": {"postalAddress": {"addressLocality": "Toronto", "addressRegion": "ON",
                                                        "addressCountry": "Canada"}}}]}
    collision = [{"id": "x", "text": "Barista", "hostedUrl": "u", "categories": {"location": "Austin, TX"}}]
    sources = FakeSources({
        ("GET", "https://api.ashbyhq.com/posting-api/job-board/maplehealth"): canadian,
        ("GET", "https://api.lever.co/v0/postings/maplehealth"): collision,
    })
    found = detect_company(settings, sources, "Maple Health", None)
    assert [(d.system, d.slug_or_url, d.confidence, d.jobs_canada) for d in found] == [
        ("ashby", "maplehealth", "possible", 1)]


def test_detect_successfactors_career_site(settings):
    sources = FakeSources({("GET", "https://jobs.scotiabank.com/search/"): httpx.Response(
        200, text=(FIXTURES / "successfactors_careers.html").read_text())})
    found = detect_company(settings, sources, "Scotiabank",
                           "https://jobs.scotiabank.com/search/?createNewAlert=false&q=&locationsearch=ontario")
    assert [(d.system, d.slug_or_url, d.confidence) for d in found] == [
        ("successfactors", "https://jobs.scotiabank.com", "likely")]


def test_detect_unreadable_page_falls_back_to_guess(settings):
    sources = FakeSources({("GET", "https://acme.example/careers"): httpx.Response(500)})
    assert detect_company(settings, sources, "Acme", "https://acme.example/careers") == []


# --- stillhiring -----------------------------------------------------------------------

def test_parse_embed_page():
    url, app = stillhiring.parse_embed_page((FIXTURES / "stillhiring_embed.html").read_text())
    assert url.startswith("https://airtable.com/v0.3/view/viwpPe6EkDqbE7Q2o/readSharedViewData?")
    assert app == "appPGrJqA2zH65k5I"


def test_parse_embed_page_changed():
    with pytest.raises(Exception, match="changed"):
        stillhiring.parse_embed_page("<html>nothing here</html>")


def test_parse_view():
    listings = {l.name: l for l in stillhiring.parse_view(fixture_json("stillhiring_view.json"))}
    docebo = listings["Docebo"]
    assert (docebo.hq_country, docebo.hq_province, docebo.hq_city) == ("CA", "ON", "Toronto")
    assert docebo.employees == 1009
    assert docebo.jobs_url == "https://jobs.ashbyhq.com/docebo"
    assert listings["EDB"].hq_country == "US"


def stillhiring_sources():
    return FakeSources({
        ("GET", stillhiring.EMBED_URL): httpx.Response(200, text=(FIXTURES / "stillhiring_embed.html").read_text()),
        ("GET", "https://airtable.com/v0.3/view/"): fixture_json("stillhiring_view.json"),
    })


def test_refresh_stores_detects_and_links(conn, settings):
    hootsuite = company(conn, "Hootsuite")
    sources = stillhiring_sources()
    summary = candidates.refresh(conn, settings, transport=sources.transport())
    data_request = sources.requests[1]
    assert data_request.headers["x-airtable-application-id"] == "appPGrJqA2zH65k5I"
    assert data_request.headers["x-requested-with"] == "XMLHttpRequest"
    assert summary.total == 12 and summary.new == 12 and summary.linked == 1 and summary.sizes == 1
    assert size(conn, hootsuite) == (1752, "stillhiring")
    hq = conn.execute("SELECT hq_city, hq_province FROM companies WHERE id = ?", (hootsuite,)).fetchone()
    assert tuple(hq) == ("Vancouver", "BC")

    pending = {c["name"]: c for c in candidates.list_candidates(conn)}
    assert "Hootsuite" not in pending  # already on the list: approved automatically
    assert "EDB" not in pending  # US HQ: hidden by default
    assert (pending["Docebo"]["detected_system"], pending["Docebo"]["detected_slug"]) == ("ashby", "docebo")
    assert pending["Shopify"]["detected_system"] is None  # company site: needs detection
    readable = {c["name"] for c in candidates.list_candidates(conn, scope="readable")}
    assert "LaunchDarkly" in readable and "EDB" not in readable


def test_refresh_again_marks_gone(conn, settings):
    candidates.refresh(conn, settings, transport=stillhiring_sources().transport())
    view = fixture_json("stillhiring_view.json")
    view["data"]["table"]["rows"] = view["data"]["table"]["rows"][1:]
    sources = stillhiring_sources()
    sources.add("GET", "https://airtable.com/v0.3/view/", view)
    summary = candidates.refresh(conn, settings, transport=sources.transport())
    assert (summary.new, summary.gone) == (0, 1)


def test_approve_and_reject(conn, settings):
    candidates.refresh(conn, settings, transport=stillhiring_sources().transport())
    by_name = {c["name"]: c for c in candidates.list_candidates(conn)}
    company_id = candidates.approve(conn, by_name["Docebo"]["id"])
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    assert (row["canadian"], row["employee_count"], row["size_source"], row["hq_city"]) == (1, 1009, "stillhiring", "Toronto")
    assert row["careers_url"] == "https://jobs.ashbyhq.com/docebo"
    board = conn.execute("SELECT system, slug_or_url, confirmed FROM boards WHERE company_id = ?", (company_id,)).fetchone()
    assert tuple(board) == ("ashby", "docebo", 1)

    # Approving with a board picked by hand, for a company the link didn't reveal.
    shopify = candidates.approve(conn, by_name["Shopify"]["id"], "greenhouse", "https://job-boards.greenhouse.io/shopify")
    assert conn.execute("SELECT slug_or_url FROM boards WHERE company_id = ?", (shopify,)).fetchone()[0] == "shopify"

    candidates.decide(conn, by_name["Petal"]["id"], "rejected")
    assert "Petal" not in {c["name"] for c in candidates.list_candidates(conn)}
    assert "Petal" in {c["name"] for c in candidates.list_candidates(conn, decision="rejected")}
    with pytest.raises(candidates.CandidateError):
        candidates.decide(conn, 9999, "rejected")


def test_approve_refuses_board_of_another_company(conn, settings):
    other = company(conn, "Someone Else")
    db.upsert_board(conn, other, "ashby", "docebo")
    candidates.refresh(conn, settings, transport=stillhiring_sources().transport())
    docebo = next(c for c in candidates.list_candidates(conn) if c["name"] == "Docebo")
    with pytest.raises(candidates.CandidateError, match="belongs to Someone Else"):
        candidates.approve(conn, docebo["id"])


def test_norm_name():
    assert candidates.norm_name("Avidbots Corp.") == candidates.norm_name("avidbots")
    assert candidates.norm_name("Dye & Durham Corporation") == "dyedurham"

