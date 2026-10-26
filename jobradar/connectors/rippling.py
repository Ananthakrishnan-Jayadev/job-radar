"""Rippling ATS public board. Paged by 20, pages counted from 0.

GET https://ats.rippling.com/api/v2/board/{company}/jobs?page=N
The page parameter name is not documented; if a later page repeats earlier
entries exactly, we stop and warn instead of looping. A job with several
locations is listed once per location; the entries are merged by id.
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import (
    FetchContext, FetchResult, clean_title, dedupe_locations, fill_details, html_to_text, iso_date, join_text, workplace,
)

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
        if more and all(i in items for i in more):
            warnings.append(f"page {page} repeated earlier jobs; read {len(items)} of {total}")
            break
        items += more
    complete = not warnings and len(items) >= total
    jobs = _merge(_job(i, board.company_canadian) for i in items)

    async def detail(job: RawJob) -> None:
        data = await client.get_json(f"{url}/{job.external_id}")
        parts = data.get("description") or {}
        if isinstance(parts, dict):
            job.description = join_text(html_to_text(parts.get("role")), html_to_text(parts.get("company")))
        else:
            job.description = html_to_text(parts)
        job.posted_at = iso_date(data.get("createdOn")) or job.posted_at

    warnings += await fill_details(jobs, ctx, client, detail, canadian_company=board.company_canadian)
    return FetchResult(jobs=jobs, total=total, complete=complete, warnings=warnings)


def _merge(jobs) -> list[RawJob]:
    """Rippling lists a job once per location: one RawJob per id, all locations."""
    merged: dict[str, RawJob] = {}
    for job in jobs:
        if job.external_id in merged:
            first = merged[job.external_id]
            first.locations = dedupe_locations(first.locations + job.locations)
            if first.workplace != job.workplace:
                first.workplace = "unknown"
        else:
            merged[job.external_id] = job
    return list(merged.values())


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
