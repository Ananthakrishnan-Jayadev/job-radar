"""Helpers shared by the connectors: text, dates, salary, workplace."""

from __future__ import annotations

import html
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser

from ..config import Settings
from ..locations import is_canadian
from ..models import Location, RawJob


@dataclass
class FetchContext:
    """What a connector may need besides the board itself."""

    settings: Settings
    # Terms for sources that search on their own side (Workday over its limit).
    search_terms: list[str] = field(default_factory=list)
    # External ids already stored with full details (Workday skips their detail page).
    known_ids: set[str] = field(default_factory=set)
    today: date | None = None  # for relative dates; tests pin it
    # Should this title get a detail page fetched? (roles.toml; None: every title)
    wants: Callable[[str], bool] | None = None

    def wanted(self, title: str) -> bool:
        return self.wants is None or self.wants(title)


@dataclass
class FetchResult:
    jobs: list[RawJob]
    total: int  # all open jobs on the board, every country
    # False when only part of the board was read (Workday search mode): the
    # scanner must not close jobs that weren't seen.
    complete: bool = True
    warnings: list[str] = field(default_factory=list)


# --- text ----------------------------------------------------------------------

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value: str | None, *, escaped: bool = False) -> str | None:
    """Plain text from an HTML description. `escaped` for Greenhouse's &lt;p&gt; form."""
    if not value:
        return None
    if escaped:
        value = html.unescape(value)
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def join_text(*parts: str | None) -> str | None:
    text = "\n\n".join(p.strip() for p in parts if p and p.strip())
    return text or None


def clean_title(value: str | None) -> str:
    return " ".join((value or "").split())


# --- detail pages ------------------------------------------------------------------

async def fill_details(jobs: list[RawJob], ctx: FetchContext, client, fetch_one: Callable[[RawJob], Awaitable[None]],
                       *, canadian_company: bool, limit: int | None = None) -> list[str]:
    """Fetch detail pages for jobs that need them; returns warnings.

    Only jobs that will be stored (in Canada), only wanted roles (roles.toml),
    only jobs not already stored with a
    description, at most `limit` per board per scan (default: settings), with a
    pause between requests. A failed detail never fails the board.
    """
    limit = ctx.settings.details_per_board if limit is None else limit
    todo = [j for j in jobs if j.external_id not in ctx.known_ids and ctx.wanted(j.title)
            and is_canadian(j.locations, canadian_company)]
    warnings, failures = [], 0
    for job in todo[:limit]:
        try:
            await fetch_one(job)
        except Exception as exc:  # noqa: BLE001 - one detail page must not fail the board
            failures += 1
            if failures <= 3:
                warnings.append(f"detail for {job.external_id} failed: {exc}")
        await client.pause()
    if len(todo) > limit:
        warnings.append(f"{len(todo) - limit} job descriptions left for the next scan")
    return warnings


# --- dates ----------------------------------------------------------------------

def iso_date(value) -> str | None:
    """YYYY-MM-DD from ISO text, "2026-10-14 11:37:16 UTC", or epoch milliseconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, UTC).date().isoformat()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
    return match.group(1) if match else None


def relative_date(text: str | None, today: date | None = None) -> str | None:
    """Workday's "Posted Today" / "Posted 3 Days Ago". "30+ Days Ago" is unknown."""
    if not text:
        return None
    today = today or date.today()
    lowered = text.lower()
    if "+" in lowered:
        return None
    if "today" in lowered:
        return today.isoformat()
    if "yesterday" in lowered:
        return (today - timedelta(days=1)).isoformat()
    match = re.search(r"(\d+)\s+days?", lowered)
    return (today - timedelta(days=int(match.group(1)))).isoformat() if match else None


# --- salary and workplace ------------------------------------------------------------

_CURRENCY_PREFIX = {"CAD": "CA$", "USD": "US$", "EUR": "€", "GBP": "£"}
_INTERVALS = {"year": "year", "annual": "year", "hour": "hour", "month": "month", "week": "week", "day": "day"}


def format_salary(low, high, currency: str | None, interval: str | None = None) -> str | None:
    """"CA$140,000 – 180,000 / year" from a range."""
    if low is None and high is None:
        return None
    prefix = _CURRENCY_PREFIX.get((currency or "").upper(), f"{currency} " if currency else "")
    amounts = [f"{int(v):,}" for v in (low, high) if v is not None]
    text = prefix + " – ".join(dict.fromkeys(amounts))
    if interval:
        period = next((p for key, p in _INTERVALS.items() if key in interval.lower()), None)
        if period:
            text += f" / {period}"
    return text


def workplace(value: str | None, remote: bool | None = None) -> str:
    """One of remote / hybrid / onsite / unknown from a source's wording."""
    key = (value or "").lower().replace("-", "").replace("_", "").replace(" ", "")
    if "hybrid" in key:
        return "hybrid"
    if "remote" in key:
        return "remote"
    if key in ("onsite", "office", "inoffice"):
        return "onsite"
    if remote:
        return "remote"
    return "unknown"


def dedupe_locations(locations: list[Location]) -> list[Location]:
    seen, out = set(), []
    for loc in locations:
        key = (loc.city, loc.province, loc.country, loc.remote)
        if key not in seen:
            seen.add(key)
            out.append(loc)
    return out
