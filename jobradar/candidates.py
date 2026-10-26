"""Candidate companies from outside sources, waiting for the user's decision.

A refresh stores every listing, marks ones that disappeared, links listings
to companies already on our list (by name), and passes their head counts on.
Nothing is scanned until the user approves it.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from dataclasses import dataclass, field

import httpx

from . import db
from .boards import normalize_board
from .config import Settings
from .detect import from_url
from .enrich import apply_size
from .http import HttpClient
from .sources import stillhiring
from .sources.stillhiring import Listing


def norm_name(name: str) -> str:
    """"Avidbots Corp." and "avidbots" compare equal."""
    name = re.sub(r"\b(inc|corp|corporation|ltd|limited|llc|co)\b\.?", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


@dataclass
class RefreshSummary:
    total: int = 0
    new: int = 0
    gone: int = 0
    canadian: int = 0
    linked: int = 0  # matched to companies already on the list
    sizes: int = 0  # head counts passed on to those companies
    details: list[str] = field(default_factory=list)


def store_listings(conn: sqlite3.Connection, source: str, listings: list[Listing], seen_at: str | None = None) -> RefreshSummary:
    seen_at = seen_at or db.now()
    summary = RefreshSummary(total=len(listings))
    companies = {norm_name(r["name"]): r["id"] for r in conn.execute("SELECT id, name FROM companies")}
    seen: list[str] = []
    for item in listings:
        seen.append(item.external_id)
        summary.canadian += item.hq_country == "CA"
        detected = from_url(item.jobs_url)
        existing = conn.execute("SELECT id, company_id FROM listings WHERE source = ? AND external_id = ?",
                                (source, item.external_id)).fetchone()
        values = (item.name, item.tagline, item.employees, item.hq_country, item.hq_province, item.hq_city,
                  item.jobs_url)
        with conn:
            if existing is None:
                summary.new += 1
                cur = conn.execute(
                    """INSERT INTO listings (name, tagline, employees, hq_country, hq_province, hq_city, jobs_url,
                                             source, external_id, detected_system, detected_slug, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*values, source, item.external_id, detected.system if detected else None,
                     detected.slug_or_url if detected else None, seen_at, seen_at),
                )
                listing_id, company_id = cur.lastrowid, None
            else:
                listing_id, company_id = existing["id"], existing["company_id"]
                conn.execute(
                    """UPDATE listings SET name = ?, tagline = ?, employees = ?, hq_country = ?, hq_province = ?,
                                           hq_city = ?, jobs_url = ?, last_seen = ?, gone_at = NULL,
                                           detected_system = COALESCE(detected_system, ?),
                                           detected_slug = COALESCE(detected_slug, ?)
                       WHERE id = ?""",
                    (*values, seen_at, detected.system if detected else None,
                     detected.slug_or_url if detected else None, listing_id),
                )
            if company_id is None and norm_name(item.name) in companies:
                company_id = companies[norm_name(item.name)]
                conn.execute("UPDATE listings SET company_id = ?, decision = 'approved' WHERE id = ?",
                             (company_id, listing_id))
                summary.linked += 1
        if company_id is not None:
            _copy_details(conn, company_id, item)
            if apply_size(conn, company_id, item.employees, "stillhiring"):
                summary.sizes += 1
    with conn:
        cur = conn.execute(
            "UPDATE listings SET gone_at = ? WHERE source = ? AND gone_at IS NULL "
            "AND external_id NOT IN (SELECT value FROM json_each(?))",
            (seen_at, source, json.dumps(seen)),
        )
    summary.gone = cur.rowcount
    return summary


def _copy_details(conn: sqlite3.Connection, company_id: int, item: Listing) -> None:
    """Fill HQ and careers link where the company has none yet."""
    with conn:
        conn.execute(
            """UPDATE companies SET hq_country = COALESCE(hq_country, ?), hq_province = COALESCE(hq_province, ?),
                                    hq_city = COALESCE(hq_city, ?), careers_url = COALESCE(careers_url, ?)
               WHERE id = ?""",
            (item.hq_country, item.hq_province, item.hq_city,
             item.jobs_url if item.jobs_url and "linkedin.com" not in item.jobs_url else None, company_id),
        )


async def refresh_async(conn: sqlite3.Connection, settings: Settings,
                        transport: httpx.AsyncBaseTransport | None = None) -> RefreshSummary:
    async with HttpClient(settings, transport=transport) as client:
        listings = await stillhiring.fetch_listings(client)
    summary = store_listings(conn, stillhiring.SOURCE, listings)
    db.set_setting(conn, "stillhiring_refreshed_at", db.now())
    return summary


def refresh(conn: sqlite3.Connection, settings: Settings, **kwargs) -> RefreshSummary:
    return asyncio.run(refresh_async(conn, settings, **kwargs))


# --- decisions ---------------------------------------------------------------------

class CandidateError(ValueError):
    pass


def approve(conn: sqlite3.Connection, listing_id: int, system: str | None = None,
            slug_or_url: str | None = None) -> int:
    """Add the listing's company (with its board, size and HQ) to the scan list. Returns its id."""
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if row is None:
        raise CandidateError(f"candidate {listing_id} not found")
    system = system or row["detected_system"]
    slug = normalize_board(system, slug_or_url or row["detected_slug"]) if system else None
    if slug:
        owner = conn.execute("SELECT c.name FROM boards b JOIN companies c ON c.id = b.company_id "
                             "WHERE b.system = ? AND b.slug_or_url = ?", (system, slug)).fetchone()
        if owner and norm_name(owner["name"]) != norm_name(row["name"]):
            raise CandidateError(f"that board already belongs to {owner['name']}")

    company_id = row["company_id"] or next(
        (r["id"] for r in conn.execute("SELECT id, name FROM companies") if norm_name(r["name"]) == norm_name(row["name"])),
        None,
    )
    if company_id is None:
        company_id = db.upsert_company(conn, row["name"], canadian=row["hq_country"] == "CA")
    if slug:
        db.upsert_board(conn, company_id, system, slug, confirmed=True, enabled=True)
    with conn:
        conn.execute("UPDATE listings SET decision = 'approved', company_id = ? WHERE id = ?", (company_id, listing_id))
    _copy_details(conn, company_id, Listing(row["external_id"], row["name"], row["tagline"], row["employees"],
                                            row["hq_country"], row["hq_province"], row["hq_city"], row["jobs_url"]))
    apply_size(conn, company_id, row["employees"], "stillhiring")
    return company_id


def decide(conn: sqlite3.Connection, listing_id: int, decision: str) -> None:
    if decision not in ("pending", "rejected"):
        raise CandidateError(f"unknown decision {decision!r}")
    with conn:
        cur = conn.execute("UPDATE listings SET decision = ? WHERE id = ?", (decision, listing_id))
    if cur.rowcount == 0:
        raise CandidateError(f"candidate {listing_id} not found")


def set_detected(conn: sqlite3.Connection, listing_id: int, system: str | None, slug: str | None, note: str) -> None:
    with conn:
        conn.execute("UPDATE listings SET detected_system = ?, detected_slug = ?, detect_note = ? WHERE id = ?",
                     (system, slug, note, listing_id))


def list_candidates(conn: sqlite3.Connection, *, decision: str = "pending", scope: str = "canada",
                    query: str | None = None) -> list[dict]:
    """Listings to review. scope "canada": Canadian HQ only; "readable": also others whose
    job board we can read (US companies with Canadian offices are common)."""
    where, params = ["l.decision = ?"], [decision]
    if scope == "canada":
        where.append("l.hq_country = 'CA'")
    elif scope == "readable":
        where.append("(l.hq_country = 'CA' OR l.detected_system IS NOT NULL)")
    if query and query.strip():
        where.append("l.name LIKE ?")
        params.append(f"%{query.strip()}%")
    rows = conn.execute(
        f"""SELECT l.*, c.name AS company_name FROM listings l LEFT JOIN companies c ON c.id = l.company_id
            WHERE {" AND ".join(where)}
            ORDER BY l.gone_at IS NOT NULL, l.hq_country != 'CA', l.detected_system IS NULL, l.name COLLATE NOCASE""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
