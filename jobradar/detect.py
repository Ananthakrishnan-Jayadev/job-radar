"""Find which job system a company uses, and its board name there.

In order of trust:
1. The careers link itself points at a job system ("jobs.ashbyhq.com/docebo"):
   certain.
2. The careers page's HTML links to or embeds one: likely.
3. Guessing the board name from the company name and trying each system:
   only plausible when the board has jobs in Canada, since names collide
   ("maple", "float" and "vector" all exist as unrelated boards).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from .boards import BoardError, normalize_board
from .config import Settings
from .connectors import CONNECTORS, FetchContext
from .http import FetchError, HttpClient
from .locations import is_canadian
from .models import Board

# Link shapes per system, matched anywhere in a URL or a page's HTML.
LINK_PATTERNS: list[tuple[str, str]] = [
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/embed/job_board(?:/js)?\?for=([\w-]+)"),
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?!embed\b)([\w-]+)"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([\w-]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([\w.-]+)"),
    ("lever", r"api\.lever\.co/v0/postings/([\w.-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([\w.%-]+)"),
    ("ashby", r"api\.ashbyhq\.com/posting-api/job-board/([\w.-]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)"),
    ("workable", r"apply\.workable\.com/(?!api\b|j/)([\w-]+)"),
    ("recruitee", r"([\w-]+)\.recruitee\.com"),
    ("breezy", r"([\w-]+)\.breezy\.hr"),
    ("rippling", r"ats\.rippling\.com/(?!api\b)([\w-]+)"),
    ("bamboohr", r"([\w-]+)\.bamboohr\.com/(?:careers|jobs)"),
    ("workday", r"(https?://[\w-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[\w-]+)"),
]
_COMPILED = [(system, re.compile(pattern)) for system, pattern in LINK_PATTERNS]
_IGNORED_SLUGS = {"www", "api", "app", "jobs", "careers", "embed", "static", "assets", "boards", "cdn"}


@dataclass
class Detected:
    system: str
    slug_or_url: str
    how: str  # "link", "page" or "guess"
    confidence: str  # "certain", "likely" or "possible"
    note: str = ""
    jobs_total: int | None = None
    jobs_canada: int | None = None


def from_text(text: str, how: str = "link") -> list[Detected]:
    """Every job-board reference in a URL or an HTML page, first match first."""
    found: dict[tuple[str, str], Detected] = {}
    for system, pattern in _COMPILED:
        for match in pattern.finditer(text):
            raw = match.group(1)
            if raw.lower() in _IGNORED_SLUGS:
                continue
            try:
                slug = normalize_board(system, raw if system == "workday" else raw.rstrip("."))
            except BoardError:
                continue
            key = (system, slug.lower())
            if key not in found:
                found[key] = Detected(system, slug, how, "certain" if how == "link" else "likely")
    return list(found.values())


def from_url(url: str | None) -> Detected | None:
    """The board a careers link points straight at, if it does."""
    if not url:
        return None
    hits = from_text(url, "link")
    return hits[0] if hits else None


def slug_guesses(name: str) -> list[str]:
    """Board names a company plausibly uses: "Top Hat" -> tophat, top-hat."""
    base = re.sub(r"\b(inc|corp|corporation|ltd|limited|llc|co|technologies|software|group)\b\.?", "",
                  name.lower())
    words = re.findall(r"[a-z0-9]+", base)
    if not words:
        return []
    guesses = ["".join(words), "-".join(words), words[0]]
    return [g for g in dict.fromkeys(guesses) if len(g) >= 3]


async def check_board(client: HttpClient, settings: Settings, system: str, slug: str,
                      company: str, canadian: bool) -> Detected | None:
    """Read a board once; None if it doesn't exist or has no jobs."""
    board = Board(id=0, company_id=0, company_name=company, company_canadian=canadian,
                  system=system, slug_or_url=slug)
    try:
        result = await CONNECTORS[system](board, client, FetchContext(settings=settings))
    except FetchError:
        return None
    if not result.jobs:
        return None
    in_canada = sum(is_canadian(j.locations, canadian) for j in result.jobs)
    return Detected(system, slug, "guess", "possible", jobs_total=result.total, jobs_canada=in_canada)


async def guess_boards(client: HttpClient, settings: Settings, name: str, canadian: bool,
                       systems: tuple[str, ...] = ("greenhouse", "lever", "ashby", "smartrecruiters",
                                                   "workable", "recruitee", "breezy", "rippling")) -> list[Detected]:
    """Try the name's slug guesses on each feed. Boards with no Canadian jobs are left out:
    for a job hunt in Canada they're useless, and they're the likeliest name collisions."""
    hits: list[Detected] = []
    for slug in slug_guesses(name):
        # Each system is a different host, so they can be asked at the same time.
        results = await asyncio.gather(*(check_board(client, settings, s, slug, name, canadian) for s in systems))
        for hit in results:
            if hit and hit.jobs_canada:
                hit.note = f"{hit.jobs_canada} of {hit.jobs_total} jobs in Canada"
                hits.append(hit)
        if hits:
            break
    return hits


async def detect_company(client: HttpClient, settings: Settings, name: str, careers_url: str | None,
                         canadian: bool, *, guess: bool = True) -> list[Detected]:
    """All the ways we can find this company's job board, most trusted first."""
    direct = from_url(careers_url)
    if direct:
        return [direct]
    found: list[Detected] = []
    if careers_url and careers_url.startswith("http") and "linkedin.com" not in careers_url:
        try:
            found = await _from_careers_page(client, careers_url)
        except FetchError:
            found = []  # unreadable page: fall back to guessing
    if not found and guess:
        found = await guess_boards(client, settings, name, canadian)
    return found


async def _from_careers_page(client: HttpClient, url: str) -> list[Detected]:
    """Boards linked from a careers page, or from its "see all jobs" page one click further."""
    response = await client.request("GET", url, headers={"Accept": "text/html"}, follow_redirects=True)
    final = str(response.url)
    redirected = from_url(final)  # the careers page redirected straight to a board
    if redirected:
        redirected.how, redirected.note = "page", f"{url} redirects there"
        return [redirected]
    found = from_text(response.text, "page")
    if not found:
        more = re.search(r'href="([^"]*(?:jobs|openings|positions|opportunities)[^"]*)"', response.text, re.I)
        if more and urljoin(final, more.group(1)) != final:
            final = urljoin(final, more.group(1))
            response = await client.request("GET", final, headers={"Accept": "text/html"}, follow_redirects=True)
            landed = from_url(str(response.url))
            found = [landed] if landed else from_text(response.text, "page")
    for hit in found:
        hit.how, hit.confidence = "page", "likely"
        hit.note = hit.note or f"linked from {final}"
    return found
