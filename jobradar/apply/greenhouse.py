"""What to put in each field of a Greenhouse application, before opening it.

Greenhouse's public Job Board API lists a job's application questions
(GET .../jobs/{id}?questions=true): label, field name, type, and the choices
of a select. Each one is answered from your profile:

1. Standard fields by name (first_name, email, resume...).
2. Your own [answers] in the profile (a piece of the question → answer).
3. Built-in rules for common questions (work authorization, sponsorship,
   LinkedIn, "how did you hear about us"...).

Anything else is left for you, and listed. The voluntary self-identification
questions (gender, race, disability, veteran status) are never answered.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ..http import HttpClient
from ..profile import Profile

QUESTIONS_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}"
# The form on its own, as company careers sites embed it; works even when a
# company's hosted Greenhouse board is switched off.
FORM_URL = "https://job-boards.greenhouse.io/embed/job_app?for={board}&token={job}"

TEXT, TEXTAREA, FILE, SELECT, MULTI = "text", "textarea", "file", "select", "multi"
_KINDS = {"input_text": TEXT, "textarea": TEXTAREA, "input_file": FILE,
          "multi_value_single_select": SELECT, "multi_value_multi_select": MULTI}


class ApplyError(Exception):
    """This job can't be filled in; the message says why."""


@dataclass
class Step:
    """One field to fill."""

    label: str
    name: str  # Greenhouse's field name: "first_name", "question_123456"...
    kind: str  # TEXT, TEXTAREA, FILE, SELECT or MULTI
    value: str  # the text, the choice's label, or the file's path
    required: bool = False
    check: bool = False  # filled from a guess worth a look (location, "how did you hear")


@dataclass
class Todo:
    """A question left for you."""

    label: str
    required: bool
    why: str = ""


@dataclass
class Plan:
    job_id: int
    title: str
    company: str
    form_url: str
    job_url: str
    phone_country: str = ""  # the country picker beside the phone number, which the API doesn't list
    steps: list[Step] = field(default_factory=list)
    todo: list[Todo] = field(default_factory=list)


def _yes_no(flag: bool | None) -> str | None:
    return None if flag is None else ("Yes" if flag else "No")


def _work_question(profile: Profile, label: str) -> str | None:
    """Work authorization: which country the question is about decides the answer."""
    if re.search(r"united states|\bu\.?s\.?a?\b|america", label):
        return _yes_no(profile.authorized_us)
    if "canada" in label or not re.search(r"united kingdom|\buk\b|europe|india|australia|germany|france", label):
        return _yes_no(profile.authorized_canada)
    return None


# (pattern on the lowercased label, answer from the profile, worth a check)
_RULES: list[tuple[str, object, bool]] = [
    (r"\bpreferred (first )?name", lambda p, l: p.preferred_name or None, False),
    (r"linkedin", lambda p, l: p.linkedin or None, False),
    (r"github", lambda p, l: p.github or None, False),
    (r"website|portfolio|personal site", lambda p, l: p.website or None, False),
    (r"pronoun", lambda p, l: p.pronouns or None, False),
    (r"(current|present|most recent|latest) (company|employer)|^(company|employer)( name)?$",
     lambda p, l: p.current_company or None, False),
    (r"(current|present|most recent|latest) (job )?(title|role|position)|^(job )?title$",
     lambda p, l: p.current_title or None, False),
    (r"sponsor", lambda p, l: _yes_no(p.needs_sponsorship), False),
    (r"(authori[sz]ed|eligible|entitled|permitted|legally able|legal right) to work|work (permit|authori[sz]ation)",
     _work_question, False),
    (r"relocat", lambda p, l: _yes_no(p.willing_to_relocate), False),
    (r"(currently )?(located|reside|residing|live|living|based) in canada",
     lambda p, l: "Yes" if p.country.lower() == "canada" else None, False),
    (r"how did you (hear|find|learn)|where did you (hear|find|learn)|referral source|how were you referred",
     lambda p, l: p.how_heard or None, True),
    (r"salary|compensation expectation|expected compensation|pay expectation|desired (pay|compensation)",
     lambda p, l: p.salary_expectation or None, False),
    (r"notice period|start date|when (can|could|would) you (start|join)|available to start|earliest .*start",
     lambda p, l: p.notice or None, False),
]


def answer(label: str, name: str, kind: str, profile: Profile) -> tuple[str | None, bool]:
    """(answer or None, worth a check) for one question."""
    fixed = {"first_name": profile.first_name, "last_name": profile.last_name, "email": profile.email,
             "phone": profile.phone, "preferred_name": profile.preferred_name}
    if name in fixed:
        return fixed[name] or None, False
    if name == "location" or re.search(r"^(current )?(location|city)\b|where are you (located|based)", label.lower()):
        return profile.location or None, True
    text = label.lower()
    for piece, reply in profile.answers.items():
        if piece in text:
            return reply, False
    for pattern, get, check in _RULES:
        if re.search(pattern, text):
            return get(profile, text), check
    return None, False


def pick_option(value: str, options: list[str]) -> str | None:
    """The choice that says *value*: "Yes" picks "Yes, I am authorized", a source picks the closest."""
    v = value.strip().lower()
    for option in options:
        if option.strip().lower() == v:
            return option
    if v in ("yes", "no"):
        return next((o for o in options if re.match(rf"\s*{v}\b", o.lower())), None)
    for option in options:
        o = option.lower()
        if v in o or o in v:
            return option
    words = set(re.findall(r"[a-z]{4,}", v))
    return next((o for o in options if words & set(re.findall(r"[a-z]{4,}", o.lower()))), None)


def make_plan(questions: list[dict], profile: Profile, resume: Path, *, job_id: int, title: str, company: str,
              form_url: str, job_url: str) -> Plan:
    plan = Plan(job_id=job_id, title=title, company=company, form_url=form_url, job_url=job_url,
                phone_country=profile.country)
    for q in questions:
        label = " ".join(str(q.get("label") or "").split())
        required = bool(q.get("required"))
        fields = [f for f in q.get("fields") or [] if f.get("type") in _KINDS]
        if not fields:
            continue
        f = fields[0]
        name, kind = str(f.get("name") or ""), _KINDS[f["type"]]
        options = [str(v.get("label")) for v in f.get("values") or [] if v.get("label") is not None]
        if kind == FILE:
            if name == "resume" or "resume" in label.lower() or re.search(r"\bcv\b", label.lower()):
                plan.steps.append(Step(label, name, FILE, str(resume), required))
            elif required:
                plan.todo.append(Todo(label, required, "attach this yourself"))
            continue
        value, check = answer(label, name, kind, profile)
        if value is None:
            plan.todo.append(Todo(label, required))
            continue
        if kind in (SELECT, MULTI):
            chosen = pick_option(value, options)
            if chosen is None:
                plan.todo.append(Todo(label, required, f"none of the choices matches {value!r}"))
                continue
            value = chosen
        plan.steps.append(Step(label, name, kind, value, required, check))
    if any(" ".join(str(q.get("label") or "").split()).lower() == "country" for q in questions):
        plan.phone_country = ""  # a Country question of the job's own: answered (or listed) above
    return plan


async def fetch_questions(client: HttpClient, board: str, job: str) -> list[dict]:
    """The job's application questions, location question included; the voluntary
    self-identification questions are left out on purpose."""
    data = await client.get_json(QUESTIONS_API.format(board=board, job=job), params={"questions": "true"})
    return list(data.get("questions") or []) + list(data.get("location_questions") or [])


async def prepare(conn: sqlite3.Connection, client: HttpClient, job_id: int, profile: Profile,
                  resume: Path) -> Plan:
    """Plan the application for a stored Greenhouse job."""
    row = conn.execute(
        "SELECT j.title, j.url, j.external_id, j.closed_at, b.system, b.slug_or_url, c.name AS company "
        "FROM jobs j JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id WHERE j.id = ?",
        (job_id,)).fetchone()
    if row is None:
        raise ApplyError(f"Job {job_id} not found.")
    if row["system"] != "greenhouse":
        raise ApplyError("Filling in applications works for Greenhouse jobs only, for now.")
    if row["closed_at"]:
        raise ApplyError("This posting has closed; it can't be applied to any more.")
    if profile.missing:
        raise ApplyError(f"Your profile is missing: {', '.join(profile.missing)} (profile.local.toml).")
    questions = await fetch_questions(client, row["slug_or_url"], row["external_id"])
    if not questions:
        raise ApplyError("Greenhouse didn't list this job's application questions.")
    return make_plan(questions, profile, resume, job_id=job_id, title=row["title"], company=row["company"],
                     form_url=FORM_URL.format(board=row["slug_or_url"], job=row["external_id"]), job_url=row["url"])
