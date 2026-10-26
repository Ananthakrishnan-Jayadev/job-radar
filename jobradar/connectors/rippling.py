"""Rippling ATS public board. Paged by 20, pages counted from 0.

GET https://ats.rippling.com/api/v2/board/{company}/jobs?page=N
The page parameter name is not documented; if a later page repeats the first
one, we stop and warn instead of looping.
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, workplace

API = "https://ats.rippling.com/api/v2/board/{slug}/jobs"
MAX_PAGES = 50


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    url = API.format(slug=board.slug_or_url)
    data = await client.get_json(url)
    items, warnings = list(data.get("items") or []), []
    total = data.get("totalItems", len(items))
    total_pages = data.get("totalPages", 1)
    page = data.get("page", 0)
    while page + 1 < min(total_pages, MAX_PAGES):
        await client.pause()
        page += 1
        more = (await client.get_json(url, params={"page": page})).get("items") or []
        known = {i["id"] for i in items}
        new = [i for i in more if i["id"] not in known]
        if not new:
            warnings.append(f"page {page} repeated earlier jobs; read {len(items)} of {total}")
            break
        items += new
    complete = not warnings and len(items) >= total
    return FetchResult(jobs=[_job(i, board.company_canadian) for i in items], total=total,
                       complete=complete, warnings=warnings)


def _job(item: dict, canadian: bool) -> RawJob:
    locations = [
        from_parts(p.get("city"), p.get("stateCode") or p.get("state"), p.get("countryCode") or p.get("country"),
                   remote=(p.get("workplaceType") or "").upper() == "REMOTE",
                   raw=p.get("name") or "", canadian_company=canadian)
        for p in item.get("locations") or []
    ]
    kinds = {workplace(p.get("workplaceType")) for p in item.get("locations") or []}
    return RawJob(
        external_id=item["id"],
        title=clean_title(item.get("name")),
        url=item.get("url") or "",
        locations=dedupe_locations(locations),
        department=(item.get("department") or {}).get("name"),
        workplace=kinds.pop() if len(kinds) == 1 else "unknown",
    )
