"""Filling in Greenhouse applications: profile, résumés, the answer plan, the
browser steps (with a stand-in page), and the API. No real browser, no network."""

import asyncio
import contextlib
import re

import pytest
from fastapi.testclient import TestClient

from conftest import FakeSources
from jobradar import db, resumes
from jobradar.apply import browser
from jobradar.apply.greenhouse import FILE, MULTI, SELECT, TEXT, ApplyError, Step, fetch_questions, make_plan, pick_option, prepare
from jobradar.apply.run import apply_job, record_submitted
from jobradar.http import HttpClient
from jobradar.models import Location, RawJob
from jobradar.profile import Profile, ProfileError, load_profile
from jobradar.web import app as web_app

PROFILE = """
[you]
first_name = "Sam"
last_name = "Lee"
email = "sam@example.com"
phone = "+1 416 555 0100"
city = "Toronto"
province = "ON"
country = "Canada"
linkedin = "https://www.linkedin.com/in/samlee"

[work]
authorized_canada = true
authorized_us = "no"
needs_sponsorship = false
willing_to_relocate = ""
how_heard = "Company careers page"

[answers]
"Years of experience with Python" = "3"
"""

# The shape Greenhouse's Job Board API gives with ?questions=true.
QUESTIONS = {
    "questions": [
        {"required": True, "label": "First Name", "fields": [{"name": "first_name", "type": "input_text", "values": []}]},
        {"required": True, "label": "Last Name", "fields": [{"name": "last_name", "type": "input_text", "values": []}]},
        {"required": True, "label": "Email", "fields": [{"name": "email", "type": "input_text", "values": []}]},
        {"required": False, "label": "Phone", "fields": [{"name": "phone", "type": "input_text", "values": []}]},
        {"required": True, "label": "Resume/CV", "fields": [
            {"name": "resume", "type": "input_file", "values": []},
            {"name": "resume_text", "type": "textarea", "values": []}]},
        {"required": False, "label": "Cover Letter", "fields": [{"name": "cover_letter", "type": "input_file"}]},
        {"required": False, "label": "LinkedIn Profile", "fields": [{"name": "question_1", "type": "input_text"}]},
        {"required": True, "label": "Are you legally authorized to work in Canada?", "fields": [
            {"name": "question_2", "type": "multi_value_single_select",
             "values": [{"label": "Yes", "value": 1}, {"label": "No", "value": 0}]}]},
        {"required": True, "label": "Will you now or in the future require sponsorship for employment visa status?",
         "fields": [{"name": "question_3", "type": "multi_value_single_select",
                     "values": [{"label": "Yes, I will", "value": 1}, {"label": "No, I won't", "value": 0}]}]},
        {"required": False, "label": "How did you hear about this job?", "fields": [
            {"name": "question_4", "type": "multi_value_single_select",
             "values": [{"label": "LinkedIn", "value": 1}, {"label": "Company Careers Page", "value": 2}]}]},
        {"required": True, "label": "How many years of experience with Python do you have?",
         "fields": [{"name": "question_5", "type": "input_text"}]},
        {"required": True, "label": "Why do you want to work at Acme?", "fields": [{"name": "question_6", "type": "textarea"}]},
        {"required": False, "label": "Are you willing to relocate?", "fields": [{"name": "question_7", "type": "input_text"}]},
        {"required": False, "label": "Hidden", "fields": [{"name": "question_8", "type": "input_hidden"}]},
    ],
    "location_questions": [
        {"required": True, "label": "Location (City)", "fields": [{"name": "location", "type": "input_text"}]}],
    "compliance": [{"type": "eeoc", "questions": [{"label": "Gender", "fields": []}]}],
}


@pytest.fixture
def profile(tmp_path):
    (tmp_path / "profile.local.toml").write_text(PROFILE)
    return load_profile(tmp_path)


def test_profile(profile, tmp_path):
    assert (profile.first_name, profile.authorized_canada, profile.authorized_us) == ("Sam", True, False)
    assert profile.willing_to_relocate is None and profile.missing == []
    assert profile.location == "Toronto, ON, Canada"
    assert profile.answers == {"years of experience with python": "3"}
    with pytest.raises(ProfileError, match="copy profile.example.toml"):
        load_profile(tmp_path / "nowhere")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "profile.local.toml").write_text("[you\n")
    with pytest.raises(ProfileError, match="mistake"):
        load_profile(tmp_path / "bad")
    assert Profile().missing == ["first_name", "last_name", "email", "phone"]


def test_example_profile_loads():
    from pathlib import Path

    example = Path(__file__).parents[1] / "profile.example.toml"
    import tomllib

    p = Profile.from_dict(tomllib.loads(example.read_text()))
    assert p.missing and p.authorized_canada is None and p.answers == {}


def test_resumes(tmp_path):
    assert resumes.list_resumes(tmp_path) == []
    name = resumes.save_resume(tmp_path, "My Résumé (2026).pdf", b"%PDF-1.4")
    again = resumes.save_resume(tmp_path, "My Résumé (2026).pdf", b"%PDF-1.4 v2")
    assert name == "My-Résumé-2026.pdf" and again == "My-Résumé-2026-2.pdf"
    assert {r["name"] for r in resumes.list_resumes(tmp_path)} == {name, again}
    assert resumes.resume_path(tmp_path, name).read_bytes() == b"%PDF-1.4"
    for bad_name, content in (("cv.exe", b"x"), ("cv.pdf", b""), ("cv.pdf", b"x" * (resumes.MAX_BYTES + 1))):
        with pytest.raises(resumes.ResumeError):
            resumes.save_resume(tmp_path, bad_name, content)
    for bad in ("../profile.local.toml", "missing.pdf"):
        with pytest.raises(resumes.ResumeError):
            resumes.resume_path(tmp_path, bad)


def test_pick_option():
    assert pick_option("Yes", ["Yes, I am", "No, I'm not"]) == "Yes, I am"
    assert pick_option("No", ["Yes", "No"]) == "No"
    assert pick_option("Company careers page", ["LinkedIn", "Company Careers Page"]) == "Company Careers Page"
    assert pick_option("Careers website", ["LinkedIn", "Company careers site"]) == "Company careers site"
    assert pick_option("Yes", ["Maybe"]) is None


def test_plan(profile, tmp_path):
    resume = tmp_path / "cv.pdf"
    questions = QUESTIONS["questions"] + QUESTIONS["location_questions"]
    plan = make_plan(questions, profile, resume, job_id=1, title="Dev", company="Acme", form_url="f", job_url="u")
    steps = {s.label: (s.kind, s.value) for s in plan.steps}
    assert steps["First Name"] == (TEXT, "Sam") and steps["Email"] == (TEXT, "sam@example.com")
    assert steps["Resume/CV"] == (FILE, str(resume))
    assert steps["LinkedIn Profile"] == (TEXT, "https://www.linkedin.com/in/samlee")
    assert steps["Are you legally authorized to work in Canada?"] == (SELECT, "Yes")
    assert steps["Will you now or in the future require sponsorship for employment visa status?"] == (
        SELECT, "No, I won't")
    assert steps["How did you hear about this job?"] == (SELECT, "Company Careers Page")
    assert steps["How many years of experience with Python do you have?"] == (TEXT, "3")  # your own answer
    assert steps["Location (City)"] == (TEXT, "Toronto, ON, Canada")
    assert {s.label for s in plan.steps if s.check} == {"How did you hear about this job?", "Location (City)"}
    assert [(t.label, t.required) for t in plan.todo] == [
        ("Why do you want to work at Acme?", True), ("Are you willing to relocate?", False)]
    assert "Gender" not in steps and "Cover Letter" not in steps and "Hidden" not in steps
    assert plan.phone_country == "Canada"


def test_current_company_and_title(profile, tmp_path):
    q = [{"label": label, "required": True, "fields": [{"name": f"q{i}", "type": "input_text"}]}
         for i, label in enumerate(["Current Company", "Current Job Title", "Most recent employer", "Title",
                                    "Who is your current or previous employer?",
                                    "What is your current or previous job title?"])]
    blank = make_plan(q, profile, tmp_path / "cv.pdf", job_id=1, title="", company="", form_url="", job_url="")
    assert len(blank.todo) == 6  # nothing in the profile: left for you
    profile.current_company, profile.current_title = "Acme Corp", "Data Analyst"
    plan = make_plan(q, profile, tmp_path / "cv.pdf", job_id=1, title="", company="", form_url="", job_url="")
    assert [s.value for s in plan.steps] == ["Acme Corp", "Data Analyst"] * 3


def test_country_questions(profile, tmp_path):
    countries = [{"label": c} for c in ("Brazil", "Canada", "US")]
    q = [{"label": "Please select the country where you currently reside.",
          "fields": [{"name": "a", "type": "multi_value_single_select", "values": countries}]},
         {"label": "Please select the country or countries you anticipate working in for the role",
          "fields": [{"name": "b[]", "type": "multi_value_multi_select", "values": countries}]},
         {"label": "Have you previously worked for Acme?", "fields": [{"name": "c", "type": "input_text"}]}]
    plan = make_plan(q, profile, tmp_path / "cv.pdf", job_id=1, title="", company="", form_url="", job_url="")
    assert [(s.name, s.value) for s in plan.steps] == [("a", "Canada"), ("b[]", "Canada")]
    assert [t.label for t in plan.todo] == ["Have you previously worked for Acme?"]


def test_a_country_question_of_its_own_turns_off_the_phone_country(profile, tmp_path):
    q = [{"label": "Country", "fields": [{"name": "country", "type": "input_text"}]}]
    plan = make_plan(q, profile, tmp_path / "cv.pdf", job_id=1, title="", company="", form_url="", job_url="")
    assert plan.phone_country == ""


def test_work_authorization_follows_the_country(profile, tmp_path):
    q = [{"label": "Are you authorized to work in the United States?",
          "fields": [{"name": "q", "type": "input_text"}]},
         {"label": "Are you eligible to work in the United Kingdom?", "fields": [{"name": "r", "type": "input_text"}]}]
    plan = make_plan(q, profile, tmp_path / "cv.pdf", job_id=1, title="", company="", form_url="", job_url="")
    assert [(s.label, s.value) for s in plan.steps] == [("Are you authorized to work in the United States?", "No")]
    assert [t.label for t in plan.todo] == ["Are you eligible to work in the United Kingdom?"]


def _greenhouse_job(conn, closed=False):
    company = db.upsert_company(conn, "Acme", canadian=True)
    board = db.upsert_board(conn, company, "greenhouse", "acme")
    job_id, _ = db.upsert_job(conn, board, RawJob("4001", "Data Analyst", "https://acme.com/careers?gh_jid=4001",
                                                  [Location("Toronto", "ON", "CA")]))
    if closed:
        with conn:
            conn.execute("UPDATE jobs SET closed_at = ? WHERE id = ?", (db.now(), job_id))
    return job_id


API = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/4001"


def _prepare(conn, settings, profile, job_id, reply=QUESTIONS):
    sources = FakeSources({("GET", API): reply})

    async def go():
        async with HttpClient(settings, transport=sources.transport()) as client:
            return await prepare(conn, client, job_id, profile, settings.root / "cv.pdf")
    return asyncio.run(go()), sources


def test_prepare(conn, settings, profile):
    job_id = _greenhouse_job(conn)
    plan, sources = _prepare(conn, settings, profile, job_id)
    assert "questions=true" in str(sources.requests[0].url)
    assert plan.form_url == "https://job-boards.greenhouse.io/embed/job_app?for=acme&token=4001"
    assert plan.job_url.endswith("gh_jid=4001") and (plan.title, plan.company) == ("Data Analyst", "Acme")
    assert any(s.name == "location" for s in plan.steps)


def test_prepare_refuses(conn, settings, profile):
    closed = _greenhouse_job(conn, closed=True)
    with pytest.raises(ApplyError, match="closed"):
        _prepare(conn, settings, profile, closed)
    lever = db.upsert_board(conn, db.upsert_company(conn, "Beta", canadian=True), "lever", "beta")
    other, _ = db.upsert_job(conn, lever, RawJob("1", "Dev", "u", [Location("Toronto", "ON", "CA")]))
    with pytest.raises(ApplyError, match="Greenhouse jobs only"):
        _prepare(conn, settings, profile, other)
    profile.phone = ""
    with conn:
        conn.execute("UPDATE jobs SET closed_at = NULL")
    with pytest.raises(ApplyError, match="missing: phone"):
        _prepare(conn, settings, profile, closed)


def test_record_submitted(conn):
    job_id = _greenhouse_job(conn)
    with conn:
        conn.execute("UPDATE jobs SET notes = 'Referred by Priya' WHERE id = ?", (job_id,))
    record_submitted(conn, job_id, "cv.pdf")
    row = conn.execute("SELECT status, applied_at, notes FROM jobs WHERE id = ?", (job_id,)).fetchone()
    assert row["status"] == "applied" and row["applied_at"]
    assert row["notes"].startswith("Referred by Priya\nApplied through Job Radar on ") and "cv.pdf" in row["notes"]
    with conn:
        conn.execute("UPDATE jobs SET status = 'interviewing' WHERE id = ?", (job_id,))
    record_submitted(conn, job_id, "cv.pdf")  # a later stage isn't moved back
    assert conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0] == "interviewing"


def test_apply_job_outcomes(conn, tmp_path, settings, profile):
    job_id = _greenhouse_job(conn)
    plan, _ = _prepare(conn, settings, profile, job_id)
    reports = []
    assert apply_job(tmp_path / "test.db", plan, "cv.pdf", reports.append, filler=lambda p, r: "closed") == "closed"
    assert conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0] == "new"
    assert apply_job(tmp_path / "test.db", plan, "cv.pdf", reports.append, filler=lambda p, r: "submitted") == "submitted"
    assert conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0] == "applied"


# --- the browser steps, against a stand-in page ----------------------------------------

def _key(name):
    return name.pattern if isinstance(name, re.Pattern) else name


class FakeLocator:
    def __init__(self, frame, key):
        self.frame, self.key = frame, key

    def count(self):
        return 1 if self.key in self.frame.elements else 0

    @property
    def first(self):
        return self

    def _el(self):
        return self.frame.elements[self.key]

    def fill(self, value, timeout=None):
        self.frame.log.append(("fill", self.key, value))

    def set_input_files(self, path, timeout=None):
        self.frame.log.append(("file", self.key, path))
        if self.frame.takes_files:
            self.frame.elements[f"text:{path.rsplit('/', 1)[-1]}"] = "SPAN"

    def evaluate(self, script):
        return self.frame.options if "options" in script else self._el()

    def select_option(self, label, timeout=None):
        self.frame.log.append(("select", self.key, label))

    def click(self, timeout=None):
        if self.key.startswith("option:") and self.key not in self.frame.elements:
            raise TimeoutError("no such option")
        self.frame.log.append(("click", self.key))
        if self.key.startswith("button:"):
            self.frame.page.chooser_open = True

    def filter(self, has_text=None):
        return FakeLocator(self.frame, f"{self.key}|{_key(has_text)}")

    def get_by_label(self, label, exact=False):
        return FakeLocator(self.frame, f"{self.key}>label:{label}")

    def check(self, timeout=None):
        self.frame.log.append(("check", self.key))

    def wait_for(self, timeout=None):
        if self.key not in self.frame.elements:
            raise TimeoutError(f"no {self.key}")


class FakeChooser:
    def __init__(self, frame):
        self.frame = frame

    def set_files(self, path):
        self.frame.log.append(("chooser", path))
        self.frame.elements[f"text:{path.rsplit('/', 1)[-1]}"] = "SPAN"


class FakeChooserPage:
    def __init__(self, frame):
        self.frame, self.chooser_open = frame, False

    @contextlib.contextmanager
    def expect_file_chooser(self, timeout=None):
        info = type("Info", (), {})()
        yield info
        assert self.chooser_open, "no file chooser opened"
        info.value = FakeChooser(self.frame)


class FakeFrame:
    """Elements by selector or label: {key: tag}."""

    def __init__(self, elements, url="https://job-boards.greenhouse.io/embed/job_app", takes_files=True,
                 options=()):
        self.elements, self.url, self.log = elements, url, []
        self.takes_files, self.options = takes_files, list(options)
        self.page = FakeChooserPage(self)

    def locator(self, selector):
        return FakeLocator(self, selector)

    def get_by_label(self, label, exact=False):
        return FakeLocator(self, f"label:{label}")

    def get_by_role(self, role, name=None, exact=False):
        return FakeLocator(self, f"{role}:{_key(name)}" if name else f"{role}:*")

    def get_by_text(self, pattern, exact=False):
        if isinstance(pattern, str):
            return FakeLocator(self, f"text:{pattern}")
        return FakeLocator(self, "thanks" if "thanks" in self.elements else "no-thanks")


def test_fill_finds_fields_by_id_name_or_label():
    frame = FakeFrame({"[id='first_name']": "INPUT", "[name='job_application[email]']": "INPUT",
                       "label:LinkedIn": "INPUT", "input[type=file]": "INPUT",
                       "[id='question_2']": "SELECT", "[id='question_3']": "INPUT", "option:No, I won't": "DIV"})
    browser._fill(frame, Step("First Name", "first_name", TEXT, "Sam"))
    browser._fill(frame, Step("Email", "email", TEXT, "sam@example.com"))
    browser._fill(frame, Step("LinkedIn", "question_1", TEXT, "https://x"))
    browser._fill(frame, Step("Resume", "resume", FILE, "/tmp/cv.pdf"))
    browser._fill(frame, Step("Authorized?", "question_2", SELECT, "Yes"))  # a real <select>
    browser._fill(frame, Step("Sponsorship?", "question_3", SELECT, "No, I won't"))  # a searchable dropdown
    assert frame.log == [
        ("fill", "[id='first_name']", "Sam"), ("fill", "[name='job_application[email]']", "sam@example.com"),
        ("fill", "label:LinkedIn", "https://x"), ("file", "input[type=file]", "/tmp/cv.pdf"),
        ("select", "[id='question_2']", "Yes"),
        ("click", "[id='question_3']"), ("fill", "[id='question_3']", "No, I won't"), ("click", "option:No, I won't"),
    ]
    with pytest.raises(browser.BrowserError):
        browser._fill(frame, Step("Missing", "question_9", TEXT, "x"))


def test_resume_goes_on_the_file_input_not_a_same_named_element():
    frame = FakeFrame({"[id='resume']": "DIV", "input[type=file][id='resume']": "INPUT"})
    browser._fill(frame, Step("Resume/CV", "resume", FILE, "/data/resumes/cv.pdf"))
    assert frame.log == [("file", "input[type=file][id='resume']", "/data/resumes/cv.pdf")]


def test_resume_falls_back_to_the_attach_button():
    # The hidden input ignores the file (the form never lists it): use Attach, like a person.
    frame = FakeFrame({"input[type=file]": "INPUT", f"button:{browser._ATTACH.pattern}": "BUTTON"},
                      takes_files=False)
    browser._fill(frame, Step("Resume/CV", "resume", FILE, "/data/resumes/cv.pdf"))
    assert frame.log[-1] == ("chooser", "/data/resumes/cv.pdf")
    stuck = FakeFrame({"input[type=file]": "INPUT"}, takes_files=False)
    with pytest.raises(browser.BrowserError, match="no file field or Attach"):
        browser._fill(stuck, Step("Resume/CV", "resume", FILE, "/data/resumes/cv.pdf"))


def test_checkbox_choices_are_ticked_by_label():
    name = "question_7[]"
    group = f"fieldset:has(input[name='{name}'])"
    frame = FakeFrame({f"input[name='{name}']:is([type=checkbox], [type=radio])": "INPUT", group: "FIELDSET",
                       f"{group}>label:Canada": "INPUT"})
    browser._fill(frame, Step("Countries you'd work in", name, MULTI, "Canada"))
    assert frame.log == [("check", f"{group}>label:Canada")]
    with pytest.raises(browser.BrowserError, match="no 'Peru'"):
        browser._fill(frame, Step("Countries you'd work in", name, MULTI, "Peru"))


def test_phone_country():
    pick = r"^\s*Canada\b"
    dropdown = FakeFrame({"[id='country']": "INPUT", f"option:*|{pick}": "DIV"})
    assert browser._phone_country(dropdown, "Canada")
    assert dropdown.log == [("click", "[id='country']"), ("fill", "[id='country']", "Canada"),
                            ("click", f"option:*|{pick}")]
    plain = FakeFrame({"label:Country": "SELECT"}, options=["United States +1", "Canada +1"])
    assert browser._phone_country(plain, "Canada")
    assert plain.log == [("select", "label:Country", "Canada +1")]
    assert browser._phone_country(FakeFrame({}), "Canada") is False


class FakePage:
    def __init__(self, frames_over_time):
        self.timeline, self.closed = list(frames_over_time), False

    @property
    def frames(self):
        return self.timeline[0]

    def is_closed(self):
        return self.timeline[0] == "closed"

    def wait_for_timeout(self, ms):
        if len(self.timeline) > 1:
            self.timeline.pop(0)


def test_watch_counts_a_submission_only_when_the_form_is_gone():
    form = FakeFrame({"#first_name, input[name='first_name'], input[name='job_application[first_name]']": "INPUT",
                      "thanks": "P"})  # thanks text beside the form doesn't count
    done = FakeFrame({"thanks": "P"})
    assert browser._watch(FakePage([[form], [form], [done]])) == "submitted"
    assert browser._watch(FakePage([[form], "closed"])) == "closed"
    assert browser._watch(FakePage([[FakeFrame({}, url="https://x/confirmation")]])) == "submitted"


# --- the API ------------------------------------------------------------------------------

def test_api_apply(conn, tmp_path, settings, profile):
    job_id = _greenhouse_job(conn)
    sources = FakeSources({("GET", API): QUESTIONS})
    seen = {}

    def filler(plan, report):
        seen["plan"] = plan
        report({"phase": "ready", "filled": [{"label": "First Name", "check": False}], "todo": []})
        return "submitted"

    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db", transport=sources.transport(),
                                           apply_filler=filler))
    setup = client.get("/api/apply/setup").json()
    assert setup["profile"]["ok"] and setup["resumes"] == [] and setup["browser"] is None
    refused = client.post(f"/api/jobs/{job_id}/apply", json={"resume": "cv.pdf"})
    assert refused.status_code == 400 and "résumé" in refused.json()["detail"]
    up = client.post("/api/resumes", files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")})
    assert up.status_code == 201 and up.json()["name"] == "cv.pdf"
    assert client.post("/api/resumes", files={"file": ("cv.txt", b"x", "text/plain")}).status_code == 400
    started = client.post(f"/api/jobs/{job_id}/apply", json={"resume": "cv.pdf"})
    assert started.status_code == 202 and started.json()["job_id"] == job_id
    client.app.state.applier.wait(5)
    state = client.get("/api/apply/current").json()
    assert state["phase"] == "submitted" and state["filled"][0]["label"] == "First Name"
    assert seen["plan"].steps[0].value == "Sam"
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "applied" and "cv.pdf" in job["notes"]


def test_api_apply_without_profile(conn, tmp_path, settings):
    job_id = _greenhouse_job(conn)
    client = TestClient(web_app.create_app(settings, db_path=tmp_path / "test.db", apply_filler=lambda p, r: "closed"))
    assert "copy profile.example.toml" in client.get("/api/apply/setup").json()["profile"]["error"]
    resumes.save_resume(tmp_path, "cv.pdf", b"%PDF")
    refused = client.post(f"/api/jobs/{job_id}/apply", json={"resume": "cv.pdf"})
    assert refused.status_code == 400 and "profile.local.toml" in refused.json()["detail"]
