"""Workable public widget feed.

GET https://apply.workable.com/api/v1/widget/accounts/{subdomain}?details=true
(details=true adds every job's description to the same response)
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, html_to_text, iso_date, workplace

API = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url), params={"details": "true"})
    jobs = [_job(i, board.company_canadian) for i in data.get("jobs", [])]
    return FetchResult(jobs=jobs, total=len(jobs))


def _job(item: dict, canadian: bool) -> RawJob:
    remote = bool(item.get("telecommuting"))
    places = [p for p in item.get("locations") or [] if not p.get("hidden")]
    locations = [
        from_parts(p.get("city"), p.get("region"), p.get("countryCode") or p.get("country"),
                   remote=remote, canadian_company=canadian)
        for p in places
    ] or [from_parts(item.get("city"), item.get("state"), item.get("country"),
                     remote=remote, canadian_company=canadian)]
    return RawJob(
        external_id=item.get("shortcode") or item["url"],
        title=clean_title(item.get("title")),
        url=item.get("url") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("published_on") or item.get("created_at")),
        department=item.get("department") or None,
        employment_type=item.get("employment_type") or None,
        workplace=workplace(None, remote),
        description=html_to_text(item.get("description")),
    )
