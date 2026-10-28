"""Experience levels: the rules, syncing, filtering, and asking Ollama (mocked)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from jobradar import cli, db, levels, queries
from jobradar.levels import level_for_years, rule_level, sync_levels, title_level, years_asked
from jobradar.models import Location, RawJob
from jobradar.roles import sync_roles
from jobradar.web import app as web_app

from conftest import FakeSources, Seq

CHAT = "http://localhost:11434/api/chat"

ROLES = """
[categories.software]
label = "Software"
include = ['engineer', 'developer']
[rules]
exclude = []
"""


@pytest.mark.parametrize("title, level", [
    ("Senior Software Engineer", "senior"),
    ("Sr. Data Engineer", "senior"),
    ("Machine Learning Intern/Co-op (Winter 2027)", "intern"),
    ("Junior Full Stack Developer Coop", "intern"),  # co-op beats junior
    ("Staff Software Engineer", "lead"),
    ("Senior Engineering Manager", "lead"),
    ("Associate Director, Data", "lead"),
    ("Associate, Data Scientist", "entry"),
    ("Software Engineer II, Payments", "mid"),
    ("Data Analyst 1", "entry"),
    ("Intermediate Developer", "mid"),
    ("Développeur.euse Sénior", "senior"),
    ("Software Engineer", None),
    ("Backend Developer (Python)", None),
])
def test_title_level(title, level):
    assert title_level(title) == level


@pytest.mark.parametrize("text, years", [
    ("<p>You have 3+ years of experience with Python.</p>", 3),
    ("<li>3-5 years of hands-on experience</li>", 3),
    ("Five (5) years' experience building APIs", 5),
    ("At least 2 years of professional software experience", 2),
    ("3 or more years of relevant experience", 3),
    ("Experience: minimum 4 years in data engineering", 4),
    ("5+ years of backend experience; 2+ years of experience with Kubernetes", 5),
    ("- 10+ years in software engineering with 5+ years in a leadership role", 10),
    ("- 7-10+ years of progressive experience in analytics", 7),
    ("- 5-7+ years in credit risk, collections, or recovery", 5),
    ("3 to 5 years in software development", 3),
    ("Au moins 5 ans d&#39;exp&eacute;rience en d&eacute;veloppement", 5),
    ("&lt;p&gt;7+ yrs experience&lt;/p&gt;", 7),
    ("We bring 65 years of experience serving clients.", None),  # the company, not the job
    ("- have 5+ years building user-facing security features", 5),
    ("- 7+ years in a customer-facing pre-sales role", 7),
    ("At least 3 years in C++ for embedded systems", 3),
    ("- 2+ ann&eacute;es d'exp&eacute;rience en ing&eacute;nierie", 2),
    ("Trusted by Canadians for 10+ years.", None),  # the company's history
    ("What we're looking for:\n\n - 5+ years working in security", 5),
    ("- gestion d'equipe technique (5 ans minimum)", 5),
    ("Join a team that ships every week.", None),
    (None, None),
])
def test_years_asked(text, years):
    assert years_asked(text) == years


def test_level_for_years():
    assert [level_for_years(y) for y in (0, 1, 2, 4, 5, 7, 8, 12)] == [
        "entry", "entry", "mid", "mid", "senior", "senior", "lead", "lead"]


def test_title_wins_over_years():
    assert rule_level("Senior AI Engineer", "1+ years with LLMs and experience in Python") == ("senior", 1, "title")
    assert rule_level("Data Engineer", "4+ years of experience") == ("mid", 4, "years")
    assert rule_level("Data Engineer", "Great team.") == (None, None, "none")


def _setup(conn, tmp_path):
    (tmp_path / "roles.toml").write_text(ROLES)
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "ashby", "acme")
    jobs = [
        ("1", "Senior Software Engineer", "5+ years of experience"),
        ("2", "Software Engineer", "2+ years of experience required"),
        ("3", "Backend Developer", "A great team that ships."),
        ("4", "Barista", "1 year of experience making coffee"),  # not a wanted role
        ("5", "Platform Engineer", None),
    ]
    ids = {}
    for ext, title, desc in jobs:
        ids[title], _ = db.upsert_job(conn, board, RawJob(
            ext, title, f"u{ext}", [Location("Toronto", "ON", "CA")], description=desc))
    sync_roles(conn, tmp_path)
    return board, ids


def _level(conn, job_id):
    return tuple(conn.execute("SELECT experience_level, min_years, level_source FROM jobs WHERE id = ?",
                              (job_id,)).fetchone())


def test_sync_only_wanted_jobs(conn, tmp_path):
    _, ids = _setup(conn, tmp_path)
    assert _level(conn, ids["Senior Software Engineer"]) == ("senior", 5, "title")
    assert _level(conn, ids["Software Engineer"]) == ("mid", 2, "years")
    assert _level(conn, ids["Backend Developer"]) == (None, None, "none")
    assert _level(conn, ids["Barista"]) == (None, None, None)  # left alone
    assert sync_levels(conn) == 0  # nothing left to do


def test_changed_description_is_worked_out_again(conn, tmp_path):
    board, ids = _setup(conn, tmp_path)
    db.upsert_job(conn, board, RawJob("3", "Backend Developer", "u3", [Location("Toronto", "ON", "CA")],
                                      description="You have 8+ years of experience."))
    assert _level(conn, ids["Backend Developer"]) == (None, None, None)
    sync_levels(conn)
    assert _level(conn, ids["Backend Developer"]) == ("lead", 8, "years")


def test_new_rules_version_redoes_rule_levels_only(conn, tmp_path, monkeypatch):
    _, ids = _setup(conn, tmp_path)
    with conn:
        conn.execute("UPDATE jobs SET experience_level = 'mid', level_source = 'ollama:m' WHERE id = ?",
                     (ids["Backend Developer"],))
    monkeypatch.setattr(levels, "RULES_VERSION", "test")
    assert sync_levels(conn) == 3  # the three rule-made rows, not the model's
    assert _level(conn, ids["Backend Developer"]) == ("mid", None, "ollama:m")


def test_filter_by_level(conn, tmp_path):
    _setup(conn, tmp_path)
    def titles(lv):
        return sorted(r["title"] for r in queries.search_jobs(conn, queries.JobFilter(levels=lv))[1])
    assert titles(["senior"]) == ["Senior Software Engineer"]
    assert titles(["mid", "senior"]) == ["Senior Software Engineer", "Software Engineer"]
    assert titles(["unknown"]) == ["Backend Developer", "Platform Engineer"]
    assert titles(["nonsense"]) == []


def test_filter_by_years_asked(conn, tmp_path):
    board, _ = _setup(conn, tmp_path)  # Senior 5, Software Engineer 2, two with no number
    db.upsert_job(conn, board, RawJob("7", "Cloud Engineer", "u7", [Location("Toronto", "ON", "CA")],
                                      description="8+ years of experience"))
    sync_roles(conn, tmp_path)
    def titles(years):
        return sorted(r["title"] for r in queries.search_jobs(conn, queries.JobFilter(years=years))[1])
    assert titles(["under3"]) == ["Software Engineer"]
    assert titles(["3to5"]) == ["Senior Software Engineer"]
    assert titles(["over5"]) == ["Cloud Engineer"]
    assert titles(["under3", "none"]) == ["Backend Developer", "Platform Engineer", "Software Engineer"]


def test_api_levels(conn, tmp_path, settings):
    _setup(conn, tmp_path)
    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db"))
    meta = client.get("/api/meta").json()
    assert meta["levels"] == ["intern", "entry", "mid", "senior", "lead", "unknown"]
    assert meta["levels_to_ask"] == 1  # Platform Engineer has no description
    assert meta["year_bands"] == ["under3", "3to5", "over5", "none"]
    assert client.get("/api/jobs?years=under3").json()["total"] == 1
    item = client.get("/api/jobs?levels=mid").json()["items"][0]
    assert (item["title"], item["level"], item["min_years"], item["level_source"]) == (
        "Software Engineer", "mid", 2, "years")
    assert "level,min_years" in client.get("/api/jobs.csv").text.splitlines()[0]


# --- Ollama --------------------------------------------------------------------------------

def _reply(level, years):
    return {"message": {"role": "assistant", "content": json.dumps({"level": level, "min_years": years})}}


def _asked(conn, job_id):
    return conn.execute("SELECT level_asked FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]


def test_ask_ollama_saves_answers(conn, tmp_path, settings):
    _, ids = _setup(conn, tmp_path)
    sources = FakeSources({("POST", CHAT): _reply("mid", 3)})
    summary = levels.run_ask_ollama(conn, settings, transport=sources.transport())
    assert (summary.asked, summary.levels_found, summary.years_found) == (1, 1, 1)
    assert _level(conn, ids["Backend Developer"]) == ("mid", 3, "ollama:gemma4:31b-cloud")
    assert _asked(conn, ids["Backend Developer"]) == "gemma4:31b-cloud"
    body = sources.bodies()[0]
    assert body["model"] == "gemma4:31b-cloud" and body["stream"] is False
    assert body["format"]["properties"]["level"]["enum"] == ["intern", "entry", "mid", "senior", "lead"]
    assert "Always choose one level" in body["messages"][0]["content"]
    assert "Backend Developer" in body["messages"][0]["content"]
    assert levels.jobs_to_ask(conn) == []  # not asked again


def test_ask_ollama_fills_only_missing_years(conn, tmp_path, settings):
    board, ids = _setup(conn, tmp_path)
    staff, _ = db.upsert_job(conn, board, RawJob("8", "Staff Engineer", "u8", [Location("Toronto", "ON", "CA")],
                                                  description="Own our platform."))
    sync_roles(conn, tmp_path)
    assert _level(conn, staff) == ("lead", None, "title")
    sources = FakeSources({("POST", CHAT): Seq([_reply("mid", 3), _reply("senior", 6)])})
    summary = levels.run_ask_ollama(conn, settings, transport=sources.transport())
    assert summary.asked == 2  # the job without a level is asked first
    assert _level(conn, staff) == ("lead", 6, "title")  # the title's level stays
    assert (summary.levels_found, summary.years_found) == (1, 2)


def test_ask_ollama_no_answer_is_not_asked_again(conn, tmp_path, settings):
    _, ids = _setup(conn, tmp_path)
    sources = FakeSources({("POST", CHAT): _reply("unknown", None)})
    summary = levels.run_ask_ollama(conn, settings, model="nemotron-3-nano:30b-cloud", transport=sources.transport())
    assert (summary.levels_found, summary.years_found) == (0, 0)
    assert _level(conn, ids["Backend Developer"]) == (None, None, "none")
    assert _asked(conn, ids["Backend Developer"]) == "nemotron-3-nano:30b-cloud"
    assert levels.jobs_to_ask(conn) == []


def test_changed_description_is_asked_again(conn, tmp_path, settings):
    board, ids = _setup(conn, tmp_path)
    levels.run_ask_ollama(conn, settings, transport=FakeSources({("POST", CHAT): _reply("unknown", None)}).transport())
    db.upsert_job(conn, board, RawJob("3", "Backend Developer", "u3", [Location("Toronto", "ON", "CA")],
                                      description="Build things with us."))
    sync_levels(conn)
    assert _asked(conn, ids["Backend Developer"]) is None
    assert len(levels.jobs_to_ask(conn)) == 1


def test_ask_ollama_dry_run_saves_nothing(conn, tmp_path, settings):
    _, ids = _setup(conn, tmp_path)
    sources = FakeSources({("POST", CHAT): _reply("senior", 6)})
    summary = levels.run_ask_ollama(conn, settings, dry_run=True, transport=sources.transport())
    assert summary.answers == [("Backend Developer", "senior", 6)]
    assert _level(conn, ids["Backend Developer"]) == (None, None, "none")


def test_ask_ollama_unusable_answer_is_retried_later(conn, tmp_path, settings):
    _setup(conn, tmp_path)
    sources = FakeSources({("POST", CHAT): {"message": {"content": "It seems senior-ish."}}})
    summary = levels.run_ask_ollama(conn, settings, transport=sources.transport())
    assert (summary.failed, summary.levels_found) == (1, 0)
    assert len(levels.jobs_to_ask(conn)) == 1


def test_ask_ollama_missing_model_or_server(conn, tmp_path, settings):
    _setup(conn, tmp_path)
    missing = FakeSources({("POST", CHAT): httpx.Response(404, json={"error": "model not found"})})
    with pytest.raises(levels.LevelsError, match="ollama run"):
        levels.run_ask_ollama(conn, settings, transport=missing.transport())
    down = FakeSources({("POST", CHAT): httpx.ConnectError("refused")})
    with pytest.raises(levels.LevelsError, match="Can't reach Ollama"):
        levels.run_ask_ollama(conn, settings, transport=down.transport())


def test_ask_ollama_stops_at_usage_limit_keeping_answers(conn, tmp_path, settings):
    board, ids = _setup(conn, tmp_path)
    db.upsert_job(conn, board, RawJob("6", "Frontend Developer", "u6", [Location("Toronto", "ON", "CA")],
                                      description="Nice people."))
    sync_roles(conn, tmp_path)
    sources = FakeSources({("POST", CHAT): Seq([_reply("entry", 0), httpx.Response(429, json={"error": "limit"})])})
    summary = levels.run_ask_ollama(conn, settings, transport=sources.transport())
    assert summary.levels_found == 1 and "usage limit" in summary.stopped
    assert _level(conn, ids["Backend Developer"])[0] == "entry"


def test_parse_answer():
    assert levels.parse_answer('Sure! {"level": "lead", "min_years": 10}') == ("lead", 10)
    assert levels.parse_answer('{"level": "mid", "min_years": 99}') == ("mid", None)
    assert levels.parse_answer("level: senior\nmin_years: null") == ("senior", None)
    assert levels.parse_answer("Level: Entry\nmin_years: 1") == ("entry", 1)
    assert levels.parse_answer("**level**: unknown") == (None, None)
    with pytest.raises(ValueError):
        levels.parse_answer('{"level": "guru", "min_years": 3}')


def test_cli_levels(tmp_path, capsys):
    db_path = tmp_path / "cli.db"
    conn = db.connect(db_path)
    _setup(conn, tmp_path)
    conn.close()
    assert cli.main(["--root", str(tmp_path), "--db", str(db_path), "levels"]) == 0
    out = capsys.readouterr().out
    assert "senior 1" in out and "mid 1" in out and "unknown 2" in out
    assert "No years of experience found: 2." in out
    assert "1 with a description miss a level or years" in out
