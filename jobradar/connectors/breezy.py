"""Breezy HR public careers feed.

GET https://{company}.breezy.hr/json
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, iso_date, workplace

API = "https://{slug}.breezy.hr/json"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url))
    if not isinstance(data, list):
        data = []
    return FetchResult(jobs=[_job(i, board.company_canadian) for i in data], total=len(data))


def _location(place: dict, canadian: bool):
    return from_parts(
        place.get("city"),
        (place.get("state") or {}).get("id") or (place.get("state") or {}).get("name"),
        (place.get("country") or {}).get("id") or (place.get("country") or {}).get("name"),
        remote=bool(place.get("is_remote")),
        raw=place.get("name") or "",
        canadian_company=canadian,
    )


def _job(item: dict, canadian: bool) -> RawJob:
    places = item.get("locations") or ([item["location"]] if item.get("location") else [])
    locations = [_location(p, canadian) for p in places]
    return RawJob(
        external_id=item["id"],
        title=clean_title(item.get("name")),
        url=item.get("url") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("published_date")),
        department=item.get("department"),
        employment_type=(item.get("type") or {}).get("name"),
        workplace=workplace(None, any(l.remote for l in locations)),
        salary_text=item.get("salary") or None,
    )
