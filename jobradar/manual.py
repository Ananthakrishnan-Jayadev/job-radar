"""Add one job by its link: for postings on job systems the app can't scan
(iCIMS, Taleo, Oracle, Dayforce, Avature...) or found anywhere else.

Reading the link: most job pages embed a schema.org JobPosting (JSON-LD) for
Google's job search, whatever system they run on, so that is read first; the
page title is the fallback. You check and complete the result before saving.

Saving: the job goes on its company's "manual" board, which is never scanned
(no connector), so a scan never closes it. The company is matched by name or
created. Same link twice opens the existing job.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from . import db, tracking
from .connectors._common import clean_title, format_salary, html_to_text, iso_date
from .detect import from_url
from .http import FetchError, HttpClient
from .locations import from_parts, normalize_country, normalize_province
from .models import JOB_STATUSES, RawJob

MANUAL = "manual"  # board system for jobs added by hand

_REMOTE_TYPES = {"telecommute", "remote"}


class ManualJobError(ValueError):
    """The job can't be saved as given; the message says what to fix."""


@dataclass
class Draft:
    """What the link's page says, for the user to check before saving."""

    url: str
    title: str = ""
    company: str = ""
    company_id: int | None = None  # an existing company with that name
    city: str = ""
    province: str = ""  # a province code, or "" when not in Canada / unknown
    country: str = ""
    remote: bool = False
    description: str = ""
    posted_at: str | None = None
    employment_type: str = ""
    salary: str = ""
    found: list[str] = field(default_factory=list)  # which fields came from the page
    note: str = ""  # why little or nothing was found

    def as_dict(self) -> dict:
        return asdict(self)


def clean_url(url: str) -> str:
    """The link without tracking parameters, fragment or trailing slash, for matching."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ManualJobError("That doesn't look like a web link (it should start with https://).")
    keep = "&".join(p for p in parts.query.split("&")
                    if p and not p.lower().startswith(("utm_", "source=", "src=", "ref=", "gh_src=", "lever-source")))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), keep, ""))


def existing_job(conn: sqlite3.Connection, url: str) -> int | None:
    """A stored job with this link (ignoring tracking parameters), if any."""
    wanted = clean_url(url)
    base = wanted.split("?")[0]
    for job_id, stored in conn.execute("SELECT id, url FROM jobs WHERE url LIKE ?", (f"%{urlsplit(base).path}%",)):
        try:
            if clean_url(stored) == wanted:
                return job_id
        except ManualJobError:
            continue
    return None


# --- reading the page --------------------------------------------------------------

class _Scripts(HTMLParser):
    """JSON-LD blocks, the <title>, and og:title / og:site_name."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_ld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in, self._buf = "ld", []
        elif tag == "title":
            self._in, self._buf = "title", []
        elif tag == "meta" and a.get("property", a.get("name", "")) in ("og:title", "og:site_name") and a.get("content"):
            self.meta[a.get("property") or a.get("name")] = a["content"]

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._in == "ld" and tag == "script":
            self.json_ld.append("".join(self._buf))
            self._in = None
        elif self._in == "title" and tag == "title":
            self.title = " ".join("".join(self._buf).split())
            self._in = None


def _postings(blocks: list[str]) -> list[dict]:
    found = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            kind = node.get("@type")
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                found.append(node)
            for key in ("@graph", "mainEntity", "itemListElement"):
                if key in node:
                    walk(node[key])

    for block in blocks:
        try:
            walk(json.loads(block, strict=False))
        except ValueError:
            continue
    return found


def _text(value) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("@value") or ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return html.unescape(str(value or "")).strip()


def draft_from_html(url: str, page: str) -> Draft:
    """Fill a Draft from a job page's HTML."""
    parser = _Scripts()
    parser.feed(page)
    draft = Draft(url=url)
    postings = _postings(parser.json_ld)
    if postings:
        p = postings[0]
        draft.title = clean_title(_text(p.get("title")))
        draft.company = _text(p.get("hiringOrganization"))
        places = p.get("jobLocation") or []
        place = (places[0] if isinstance(places, list) and places else places) or {}
        address = place.get("address", {}) if isinstance(place, dict) else {}
        if isinstance(address, dict):
            draft.city = _text(address.get("addressLocality"))
            region = _text(address.get("addressRegion"))
            draft.country = normalize_country(_text(address.get("addressCountry"))) or ""
            draft.province = (normalize_province(region) or "") if draft.country in ("CA", "") else ""
            if not draft.province and draft.city and draft.country in ("CA", ""):
                # "Toronto" alone: the city list knows its province.
                loc = from_parts(draft.city, region or None, draft.country or None)
                if loc.country == "CA" and loc.province:
                    draft.province = loc.province
            if draft.province:
                draft.country = "CA"
        kinds = p.get("jobLocationType") or ""
        kinds = kinds if isinstance(kinds, list) else [kinds]
        draft.remote = any(str(k).lower() in _REMOTE_TYPES for k in kinds)
        draft.description = html_to_text(_text(p.get("description")), escaped=True) or ""
        draft.posted_at = iso_date(p.get("datePosted"))
        kind = p.get("employmentType") or ""
        draft.employment_type = ", ".join(kind) if isinstance(kind, list) else str(kind)
        salary = p.get("baseSalary")
        if isinstance(salary, dict) and isinstance(salary.get("value"), dict):
            v = salary["value"]
            draft.salary = format_salary(v.get("minValue") or v.get("value"), v.get("maxValue"),
                                         salary.get("currency"), v.get("unitText")) or ""
        draft.found = [k for k in ("title", "company", "city", "province", "description", "posted_at")
                       if getattr(draft, k)]
    if not draft.title:
        draft.title = clean_title(parser.meta.get("og:title") or parser.title)
        if draft.title:
            draft.found.append("title (from the page title, check it)")
    if not draft.company:
        draft.company = parser.meta.get("og:site_name", "")
    if not postings:
        draft.note = ("This page doesn't describe the job in a form the app can read, so fill in the details "
                      "yourself.")
    return draft


async def read_link(conn: sqlite3.Connection, client: HttpClient, url: str) -> Draft:
    """Fetch the page behind *url* and draft the job; never raises for an unreadable page."""
    url = url.strip()
    clean_url(url)  # a usable link at all?
    try:
        draft = draft_from_html(url, await client.get_text(url))
    except FetchError as exc:
        draft = Draft(url=url, note=f"The page couldn't be read ({exc}). Fill in the details yourself.")
    _match_company(conn, draft)
    return draft


def _match_company(conn: sqlite3.Connection, draft: Draft) -> None:
    """Point the draft at a company already in the list: by the link's job board, else by name."""
    board = from_url(draft.url)
    if board:
        row = conn.execute("SELECT c.id, c.name FROM boards b JOIN companies c ON c.id = b.company_id "
                           "WHERE b.system = ? AND b.slug_or_url = ?", (board.system, board.slug_or_url)).fetchone()
        if row:
            draft.company_id, draft.company = row["id"], row["name"]
            return
    if draft.company:
        row = conn.execute("SELECT id, name FROM companies WHERE name = ? COLLATE NOCASE",
                           (draft.company.strip(),)).fetchone()
        if row:
            draft.company_id, draft.company = row["id"], row["name"]


# --- saving --------------------------------------------------------------------------

def save_job(conn: sqlite3.Connection, *, url: str, title: str, company: str = "", company_id: int | None = None,
             city: str = "", province: str = "", remote: bool = False, description: str = "",
             posted_at: str | None = None, employment_type: str = "", salary: str = "",
             status: str = "saved") -> tuple[int, bool]:
    """Store a job added by hand. Returns (job id, whether it's new); an existing
    job with the same link is returned as it is."""
    if (found := existing_job(conn, url)) is not None:
        return found, False
    title = " ".join(title.split())
    if not title:
        raise ManualJobError("Give the job a title.")
    province = (province or "").strip().upper()
    if province and normalize_province(province) != province:
        raise ManualJobError(f"Unknown province {province!r}.")
    if not province and not remote:
        raise ManualJobError("Pick a province, or mark the job as remote in Canada: the app only lists Canadian jobs.")
    if status not in JOB_STATUSES:
        raise ManualJobError(f"Unknown status {status!r}.")
    if company_id is not None:
        if conn.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
            raise ManualJobError(f"Company {company_id} not found.")
    elif company.strip():
        row = conn.execute("SELECT id FROM companies WHERE name = ? COLLATE NOCASE", (company.strip(),)).fetchone()
        company_id = row["id"] if row else db.upsert_company(conn, " ".join(company.split()), canadian=True)
    else:
        raise ManualJobError("Say which company the job is at.")

    board = db.upsert_board(conn, company_id, MANUAL, str(company_id), enabled=False)
    location = from_parts(city or None, province or None, "CA" if province else None, remote=remote,
                          raw=", ".join(p for p in (city, province) if p) or ("Remote, Canada" if remote else ""))
    if remote and not province:
        location.country = "CA"
    job = RawJob(
        external_id=clean_url(url), title=title, url=url.strip(), locations=[location],
        posted_at=iso_date(posted_at) if posted_at else None, employment_type=employment_type or None,
        workplace="remote" if remote else "unknown", salary_text=salary or None,
        description=description.strip() or None,
    )
    job_id, _ = db.upsert_job(conn, board, job)
    if status != "new":
        tracking.update_job(conn, job_id, status=status)
    return job_id, True
