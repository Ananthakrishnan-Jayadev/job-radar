"""Experience level of each wanted job: intern, entry, mid, senior or lead.

Rules first, for every job roles.toml wants (no requests, same answer every
time): a level word in the title wins ("Senior", "Intern", "Staff", "II"...);
otherwise the years of experience the description asks for, the smallest
number it names, so a job you might qualify for is never hidden.

Jobs the rules can't place can be sent to a local Ollama model on request
(`jobradar levels --ai`, or the button on the Jobs page). Nothing calls it
during a scan.

level_source: NULL = not worked out yet, "title" / "years" = the rules,
"none" = the rules found nothing (Ollama may try), "ollama:<model>" = asked
the model (level NULL if it couldn't tell either; it isn't asked again).
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from . import db
from .config import Settings
from .roles import fold

LEVELS = ("intern", "entry", "mid", "senior", "lead")
UNKNOWN_LEVEL = "unknown"  # filter value for jobs without a level

# Bump when the rules below change: rule-made levels are worked out again.
RULES_VERSION = "1"

_TITLE_RULES = [
    ("intern", r" (?:intern|interns|internship|co op|coop|stagiaire|summer student|student) "),
    ("lead", r" (?:lead|leader|staff|principal|manager|director|head of|vp|vice president|chief|distinguished) "),
    ("senior", r" (?:senior|sr|sr\.|snr) "),
    ("mid", r" (?:intermediate|mid level|intermediaire) "),
    ("entry", r" (?:junior|jr|jr\.|entry level|new grad|new graduate|graduate|early career|associate) "),
]
_TITLE_RULES = [(level, re.compile(rx)) for level, rx in _TITLE_RULES]
# "Software Engineer II", "Data Analyst 1".
_GRADE = re.compile(r" (?:engineer|developer|scientist|analyst|architect|specialist|programmer|consultant)"
                    r" (i|ii|iii|iv|1|2|3|4) ")
_GRADE_LEVEL = {"i": "entry", "1": "entry", "ii": "mid", "2": "mid", "iii": "senior", "3": "senior",
                "iv": "senior", "4": "senior"}

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15}
_NUM = r"(\d{1,2}|" + "|".join(_WORDS) + r")(?:\s*\(\d{1,2}\+?\))?"
_YEARS = [
    # "3+ years of experience", "3-5 yrs of hands-on experience", "five (5) years' experience"
    re.compile(rf"\b{_NUM}\s*(?:\+|plus|or more)?\s*(?:(?:-|to|or)\s*\d{{1,2}}\s*\+?\s*)?(?:years?|yrs?)\b[^.;\n]{{0,60}}?\bexperience"),
    # "experience: 3+ years", "experience (minimum 2 years)"
    re.compile(rf"\bexperience\b[^.;\n]{{0,25}}?\b{_NUM}\s*\+?\s*(?:years?|yrs?)\b"),
    # "5 ans d'experience" (accents are removed first)
    re.compile(rf"\b{_NUM}\s*(?:\+|plus)?\s*(?:(?:-|a)\s*\d{{1,2}}\s*)?ans?\b[^.;\n]{{0,40}}?\bexperience"),
]
MAX_YEARS = 15  # "65 years of experience serving clients" is the company, not the job


def title_level(title: str) -> str | None:
    t = fold(title)
    for level, rx in _TITLE_RULES:
        if rx.search(t):
            return level
    if m := _GRADE.search(t):
        return _GRADE_LEVEL[m.group(1)]
    return None


def plain_text(description: str) -> str:
    """Lowercase text without tags, entities or accents."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(description)))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[ \t\r\f\v ]+", " ", text.replace("’", "'").replace("–", "-").replace("—", "-"))


def years_asked(description: str | None) -> int | None:
    """The smallest number of years of experience the description asks for."""
    if not description:
        return None
    text = plain_text(description)
    found = []
    for rx in _YEARS:
        for m in rx.finditer(text):
            value = int(m.group(1)) if m.group(1).isdigit() else _WORDS[m.group(1)]
            if value <= MAX_YEARS:
                found.append(value)
    return min(found) if found else None


def level_for_years(years: int) -> str:
    if years <= 1:
        return "entry"
    if years <= 4:
        return "mid"
    if years <= 7:
        return "senior"
    return "lead"


def rule_level(title: str, description: str | None) -> tuple[str | None, int | None, str]:
    """(level, years asked, source): the title first, then the years."""
    years = years_asked(description)
    if level := title_level(title):
        return level, years, "title"
    if years is not None:
        return level_for_years(years), years, "years"
    return None, None, "none"


def sync_levels(conn: sqlite3.Connection) -> int:
    """Work out levels for wanted jobs that don't have one yet. Returns jobs updated.

    Jobs roles.toml leaves out are skipped (without a roles.toml, every job counts).
    """
    if db.get_setting(conn, "levels_version") != RULES_VERSION:
        with conn:
            conn.execute("UPDATE jobs SET experience_level = NULL, min_years = NULL, level_source = NULL "
                         "WHERE level_source IN ('title', 'years', 'none')")
        db.set_setting(conn, "levels_version", RULES_VERSION)
    rows = conn.execute("SELECT id, title, description FROM jobs "
                        "WHERE level_source IS NULL AND COALESCE(role_wanted, 1) = 1").fetchall()
    if not rows:
        return 0
    updates = [(*rule_level(title, description), job_id) for job_id, title, description in rows]
    with conn:
        conn.executemany("UPDATE jobs SET experience_level = ?, min_years = ?, level_source = ? WHERE id = ?",
                         updates)
    return len(updates)


# --- asking Ollama about the jobs the rules can't place --------------------------------

class LevelsError(Exception):
    """Ollama can't be used right now (not running, not signed in, out of quota)."""


_PROMPT = """Read this job posting and say what experience level it is for.

Levels:
- intern: internship, co-op or student role
- entry: new graduate, junior, or 0-1 years of experience
- mid: 2-4 years of experience
- senior: 5-7 years, or a senior role
- lead: 8+ years, or staff, principal, lead, manager or director
- unknown: the posting gives no clue

min_years: the smallest number of years of experience the posting asks for, or null if it doesn't say.

Title: {title}

Posting:
{text}"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": [*LEVELS, UNKNOWN_LEVEL]},
        "min_years": {"type": ["integer", "null"]},
    },
    "required": ["level", "min_years"],
}


def jobs_to_ask(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Open wanted jobs with a description that the rules couldn't place."""
    return conn.execute("SELECT id, title, description FROM jobs WHERE level_source = 'none' "
                        "AND closed_at IS NULL AND description IS NOT NULL ORDER BY id").fetchall()


def parse_answer(content: str) -> tuple[str | None, int | None]:
    """(level or None, years) from the model's JSON reply; ValueError if it isn't one."""
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("no JSON in the answer")
    data = json.loads(match.group(0))
    level = data.get("level")
    if level not in (*LEVELS, UNKNOWN_LEVEL):
        raise ValueError(f"unexpected level {level!r}")
    years = data.get("min_years")
    years = years if isinstance(years, int) and 0 <= years <= MAX_YEARS else None
    return (None if level == UNKNOWN_LEVEL else level), years


@dataclass
class AskSummary:
    model: str
    asked: int = 0
    found: int = 0
    unknown: int = 0
    failed: int = 0
    stopped: str | None = None  # why it stopped early
    answers: list[tuple[str, str | None, int | None]] = field(default_factory=list)  # (title, level, years)


async def ask_ollama(conn: sqlite3.Connection, settings: Settings, *, model: str | None = None,
                     limit: int | None = None, dry_run: bool = False,
                     transport: httpx.AsyncBaseTransport | None = None,
                     progress: Callable[[int, int], None] | None = None) -> AskSummary:
    """Ask the model about each job the rules couldn't place, one at a time,
    saving each answer as it comes (a stopped run keeps what it got).
    dry_run: ask but save nothing, to compare models."""
    o = settings.ollama
    summary = AskSummary(model=model or o.model)
    rows = jobs_to_ask(conn)[:limit] if limit else jobs_to_ask(conn)
    async with httpx.AsyncClient(base_url=o.url, timeout=o.timeout_seconds, transport=transport) as client:
        for i, row in enumerate(rows):
            if progress:
                progress(i, len(rows))
            body = {
                "model": summary.model, "stream": False, "format": _SCHEMA, "options": {"temperature": 0},
                "messages": [{"role": "user", "content": _PROMPT.format(
                    title=row["title"], text=plain_text(row["description"])[:o.max_chars])}],
            }
            try:
                response = await client.post("/api/chat", json=body)
            except httpx.TimeoutException:
                summary.failed += 1
                continue
            except httpx.TransportError as exc:
                raise LevelsError(f"Can't reach Ollama at {o.url}. Is it running (`ollama serve`)?") from exc
            if response.status_code != 200:
                summary.stopped = _stop_reason(response, summary.model)
                break
            summary.asked += 1
            try:
                level, years = parse_answer(response.json().get("message", {}).get("content", ""))
            except ValueError:
                summary.failed += 1
                continue
            summary.found += level is not None
            summary.unknown += level is None
            summary.answers.append((row["title"], level, years))
            if not dry_run:
                with conn:
                    conn.execute("UPDATE jobs SET experience_level = ?, min_years = ?, level_source = ? "
                                 "WHERE id = ?", (level, years, f"ollama:{summary.model}", row["id"]))
    if summary.stopped and summary.asked == 0:
        raise LevelsError(summary.stopped)
    return summary


def _stop_reason(response: httpx.Response, model: str) -> str:
    try:
        detail = response.json().get("error", "")
    except ValueError:
        detail = response.text[:200]
    if response.status_code == 404:
        return f"Ollama doesn't have {model}. Run `ollama run {model}` once, then try again."
    if response.status_code in (401, 403):
        return f"Ollama needs you to sign in for cloud models: run `ollama signin`. ({detail})"
    if response.status_code == 429:
        return f"Ollama's usage limit is reached; try again later. ({detail})"
    return f"Ollama answered HTTP {response.status_code}: {detail}"


def run_ask_ollama(conn: sqlite3.Connection, settings: Settings, **kwargs) -> AskSummary:
    return asyncio.run(ask_ollama(conn, settings, **kwargs))
