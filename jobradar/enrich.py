"""Company size (employee count) from several sources, best one wins.

Precedence: manual > stillhiring > wikidata > estimate. A source never
overwrites a better one; the same source may refresh its own number.

Wikidata is read through its regular API (wbsearchentities + wbgetentities),
not the SPARQL service, which rate-limits hard. A match is used only when it
is clear: one company-type item with a head count, in Canada for a Canadian
company. Anything less certain is stored as a suggestion the user can accept
on the company page.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from . import db
from .config import Settings
from .http import FetchError, HttpClient

PRIORITY = {"estimate": 1, "wikidata": 2, "stillhiring": 3, "manual": 4}

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
CANADA = "Q16"
# "instance of" values that mean a company (business, enterprise, public company, bank...).
COMPANY_TYPES = {
    "Q4830453", "Q6881511", "Q891723", "Q783794", "Q22687", "Q1589009", "Q18388277",
    "Q219577", "Q658255", "Q167037", "Q1058914", "Q210167", "Q2085381",
}


def apply_size(conn: sqlite3.Connection, company_id: int, count: int | None, source: str,
               *, wikidata_id: str | None = None) -> bool:
    """Store *count* from *source* unless the company has a size from a better source."""
    if count is None or count < 0:
        return False
    row = conn.execute("SELECT size_source FROM companies WHERE id = ?", (company_id,)).fetchone()
    if row is None:
        return False
    current = row["size_source"]
    if current and PRIORITY[current] > PRIORITY[source]:
        return False
    with conn:
        conn.execute(
            "UPDATE companies SET employee_count = ?, size_source = ?, size_updated_at = ?, "
            "size_suggestion = NULL, wikidata_id = COALESCE(?, wikidata_id) WHERE id = ?",
            (int(count), source, db.now(), wikidata_id, company_id),
        )
    return True


def suggest_size(conn: sqlite3.Connection, company_id: int, suggestion: dict | None) -> None:
    with conn:
        conn.execute("UPDATE companies SET size_suggestion = ? WHERE id = ?",
                     (json.dumps(suggestion) if suggestion else None, company_id))


def accept_suggestion(conn: sqlite3.Connection, company_id: int) -> bool:
    row = conn.execute("SELECT size_suggestion FROM companies WHERE id = ?", (company_id,)).fetchone()
    if row is None or not row["size_suggestion"]:
        return False
    s = json.loads(row["size_suggestion"])
    return apply_size(conn, company_id, s["employees"], s["source"], wikidata_id=s.get("wikidata_id"))


# --- estimate ----------------------------------------------------------------------

def estimate_size(total_open: int | None, systems: list[str]) -> int | None:
    """A rough head count from open roles worldwide and the job system.

    Returns the low end of a size band; shown as "estimated". Workday is used
    almost only by large employers.
    """
    if not total_open and "workday" not in systems:
        return None
    n = total_open or 0
    if "workday" in systems or n >= 500:
        return 5000 if n >= 300 else 1000
    if n >= 100:
        return 1000
    if n >= 25:
        return 200
    if n >= 5:
        return 50
    return 10


def estimate_missing(conn: sqlite3.Connection) -> int:
    """Estimate sizes for companies that have none (or only an older estimate)."""
    rows = conn.execute("""
        SELECT c.id, SUM(b.total_open) AS total, GROUP_CONCAT(b.system) AS systems
        FROM companies c JOIN boards b ON b.company_id = c.id AND b.enabled = 1
        WHERE c.size_source IS NULL OR c.size_source = 'estimate'
        GROUP BY c.id
    """).fetchall()
    done = 0
    for r in rows:
        count = estimate_size(r["total"], (r["systems"] or "").split(","))
        done += apply_size(conn, r["id"], count, "estimate")
    return done


# --- Wikidata ------------------------------------------------------------------------

@dataclass
class WikidataMatch:
    wikidata_id: str
    label: str
    description: str
    employees: int
    as_of: str | None
    in_canada: bool
    exact_name: bool

    def as_suggestion(self) -> dict:
        return {"source": "wikidata", "employees": self.employees, "as_of": self.as_of,
                "wikidata_id": self.wikidata_id, "label": self.label, "description": self.description,
                "url": f"https://www.wikidata.org/wiki/{self.wikidata_id}"}


def _claim_values(entity: dict, prop: str) -> list:
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if value is not None:
            out.append((value, claim))
    return out


def latest_employees(entity: dict) -> tuple[int, str | None] | None:
    """The most recent "number of employees" (P1128), by its "point in time" qualifier."""
    best = None
    for value, claim in _claim_values(entity, "P1128"):
        try:
            amount = int(float(value["amount"]))
        except (KeyError, TypeError, ValueError):
            continue
        times = [q["datavalue"]["value"]["time"] for q in claim.get("qualifiers", {}).get("P585", [])
                 if q.get("datavalue")]
        when = times[0].lstrip("+")[:10].replace("-00", "") if times else None
        key = (when or "", claim.get("rank") == "preferred")
        if best is None or key > best[0]:
            best = (key, amount, when)
    return (best[1], best[2]) if best else None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def pick_match(name: str, canadian: bool, search: list[dict], entities: dict[str, dict]) -> tuple[WikidataMatch | None, bool]:
    """(best match, whether it's certain enough to use without asking)."""
    candidates: list[WikidataMatch] = []
    for hit in search:
        entity = entities.get(hit["id"])
        if not entity:
            continue
        types = {v.get("id") for v, _ in _claim_values(entity, "P31") if isinstance(v, dict)}
        if not types & COMPANY_TYPES:
            continue
        employees = latest_employees(entity)
        if employees is None:
            continue
        countries = {v.get("id") for v, _ in _claim_values(entity, "P17") if isinstance(v, dict)}
        label = entity.get("labels", {}).get("en", {}).get("value") or hit.get("label") or hit["id"]
        matched_text = hit.get("match", {}).get("text") or label
        candidates.append(WikidataMatch(
            wikidata_id=hit["id"], label=label,
            description=entity.get("descriptions", {}).get("en", {}).get("value", ""),
            employees=employees[0], as_of=employees[1], in_canada=CANADA in countries,
            exact_name=_norm(matched_text) == _norm(name) or _norm(label) == _norm(name),
        ))
    if not candidates:
        return None, False
    if canadian:
        local = [c for c in candidates if c.in_canada]
        if local:
            candidates = local
    best = candidates[0]
    certain = len(candidates) == 1 and best.exact_name and (best.in_canada or not canadian)
    return best, certain


async def wikidata_lookup(client: HttpClient, companies: list[tuple[str, bool]],
                          progress: Callable[[int], None] | None = None) -> dict[str, tuple[WikidataMatch | None, bool]]:
    """Look up many companies: {name: (match, certain)}. One search per name, entities in batches."""
    searches: dict[str, list[dict]] = {}
    for i, (name, _) in enumerate(companies):
        try:
            data = await client.get_json(WIKIDATA_API, params={
                "action": "wbsearchentities", "search": name, "language": "en", "type": "item",
                "limit": 7, "format": "json"})
            searches[name] = data.get("search", [])
        except FetchError:
            searches[name] = []
        if progress:
            progress(i + 1)
        await client.pause()

    ids = sorted({hit["id"] for hits in searches.values() for hit in hits})
    entities: dict[str, dict] = {}
    for start in range(0, len(ids), 50):
        data = await client.get_json(WIKIDATA_API, params={
            "action": "wbgetentities", "ids": "|".join(ids[start:start + 50]),
            "props": "claims|labels|descriptions", "languages": "en", "format": "json"})
        entities.update(data.get("entities", {}))
        await client.pause()
    return {name: pick_match(name, canadian, searches[name], entities) for name, canadian in companies}


@dataclass
class EnrichSummary:
    looked_up: int = 0
    from_wikidata: int = 0
    suggested: int = 0
    estimated: int = 0
    details: list[str] = field(default_factory=list)


async def enrich_async(conn: sqlite3.Connection, settings: Settings, *, company: str | None = None,
                       transport: httpx.AsyncBaseTransport | None = None,
                       progress: Callable[[int, int], None] | None = None) -> EnrichSummary:
    """Fill sizes: Wikidata for companies without a better source, then estimates."""
    sql = "SELECT id, name, canadian, size_source FROM companies"
    params: list = []
    if company:
        sql += " WHERE name = ? COLLATE NOCASE"
        params.append(company)
    rows = [r for r in conn.execute(sql, params).fetchall()
            if r["size_source"] is None or PRIORITY[r["size_source"]] <= PRIORITY["wikidata"]]
    summary = EnrichSummary(looked_up=len(rows))
    if rows:
        async with HttpClient(settings, transport=transport) as client:
            results = await wikidata_lookup(
                client, [(r["name"], bool(r["canadian"])) for r in rows],
                progress=(lambda done: progress(done, len(rows))) if progress else None,
            )
        for r in rows:
            match, certain = results[r["name"]]
            if match and certain:
                if apply_size(conn, r["id"], match.employees, "wikidata", wikidata_id=match.wikidata_id):
                    summary.from_wikidata += 1
                    summary.details.append(f"{r['name']}: {match.employees:,} (Wikidata, {match.as_of or 'no date'})")
            elif match:
                suggest_size(conn, r["id"], match.as_suggestion())
                summary.suggested += 1
                summary.details.append(f"{r['name']}: maybe {match.employees:,} ({match.label}: {match.description})")
    summary.estimated = estimate_missing(conn) if not company else 0
    return summary


def run_enrich(conn: sqlite3.Connection, settings: Settings, **kwargs) -> EnrichSummary:
    return asyncio.run(enrich_async(conn, settings, **kwargs))
