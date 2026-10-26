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
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

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
    ("jazzhr", r"([\w-]+)\.applytojob\.com"),
    ("jazzhr", r"app\.jazz\.co/(?:feeds/export/jobs|widgets/[\w/]+?)/([\w-]+)"),
]
_COMPILED = [(system, re.compile(pattern)) for system, pattern in LINK_PATTERNS]
_SUCCESSFACTORS_MARKERS = ("rmkcdn.successfactors.com", "j2w.init(")


def _is_successfactors(html: str) -> bool:
    return any(marker in html for marker in _SUCCESSFACTORS_MARKERS)


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
    # Only the whole name: the first word alone ("block" for "Block 64",
    # "contractor" for "Contractor Compliance") matched other companies' boards.
    guesses = ["".join(words), "-".join(words)]
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
                       systems: tuple[str, ...] = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable",
                                                   "recruitee", "breezy", "rippling", "bamboohr",
                                                   "jazzhr")) -> list[Detected]:
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
    if not found and _is_successfactors(response.text):
        # SuccessFactors career sites live on the company's own domain.
        found = [Detected("successfactors", f"https://{urlsplit(final).netloc.lower()}", "page", "likely",
                          note=f"{urlsplit(final).netloc} is a SAP SuccessFactors career site")]
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


# --- filling in boards for companies that have none --------------------------------------

@dataclass
class FindSummary:
    checked: int = 0
    found: int = 0
    unconfirmed: int = 0  # guessed from the name: added, but flagged for the user to check
    details: list[str] = field(default_factory=list)


async def find_missing_boards(conn, settings: Settings, *, transport=None, company: str | None = None,
                              progress=None) -> FindSummary:
    """Detect and add a job board for every company that has none.

    A board found from a careers link or page is added as confirmed; one guessed
    from the name is added unconfirmed (it may be another company's).
    """
    from . import db

    sql = """SELECT c.id, c.name, c.careers_url, c.canadian FROM companies c
             WHERE NOT EXISTS (SELECT 1 FROM boards b WHERE b.company_id = c.id)"""
    params: list = []
    if company:
        sql += " AND c.name = ? COLLATE NOCASE"
        params.append(company)
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY c.name", params)]
    summary = FindSummary(checked=len(rows))
    limit = asyncio.Semaphore(4)  # a few companies at once; each host is still limited per request
    done = 0

    async with HttpClient(settings, transport=transport) as client:
        async def one(row: dict) -> None:
            nonlocal done
            async with limit:
                hits = await detect_company(client, settings, row["name"], row["careers_url"], bool(row["canadian"]))
            done += 1
            if progress:
                progress(done, len(rows))
            if not hits:
                summary.details.append(f"{row['name']}: no job board found")
                return
            best = hits[0]
            owner = conn.execute("SELECT company_id FROM boards WHERE system = ? AND slug_or_url = ?",
                                 (best.system, best.slug_or_url)).fetchone()
            if owner and owner[0] != row["id"]:
                summary.details.append(f"{row['name']}: {best.system}:{best.slug_or_url} belongs to another company")
                return
            confirmed = best.confidence != "possible"
            db.upsert_board(conn, row["id"], best.system, best.slug_or_url, confirmed=confirmed, enabled=True)
            summary.found += 1
            summary.unconfirmed += not confirmed
            how = "guessed from the name, unconfirmed" if not confirmed else best.note or "from its careers link"
            summary.details.append(f"{row['name']}: {best.system}:{best.slug_or_url} ({how})")

        await asyncio.gather(*(one(r) for r in rows))
    summary.details.sort()
    return summary
