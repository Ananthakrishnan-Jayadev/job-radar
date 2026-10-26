"""Greenhouse Job Board API (official, public).

GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import parse_text
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, html_to_text, iso_date, workplace

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url), params={"content": "true"})
    jobs = [_job(item, board.company_canadian) for item in data.get("jobs", [])]
    total = (data.get("meta") or {}).get("total") or len(jobs)
    return FetchResult(jobs=jobs, total=total)


def _job(item: dict, canadian: bool) -> RawJob:
    place = (item.get("location") or {}).get("name") or ""
    remote = "remote" in place.lower()
    # Offices carry fuller text ("Toronto, Ontario, Canada") than the location name.
    office_places = [o.get("location") for o in item.get("offices") or [] if o.get("location")]
    locations = []
    for text in office_places or [place]:
        locations += parse_text(text, canadian_company=canadian, remote=remote)
    if office_places and remote:
        locations += parse_text(place, canadian_company=canadian)

    employment = next(
        (m.get("value") for m in item.get("metadata") or []
         if (m.get("name") or "").lower() == "employment type" and isinstance(m.get("value"), str)),
        None,
    )
    departments = item.get("departments") or []
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("title")),
        url=item.get("absolute_url") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("first_published") or item.get("updated_at")),
        department=departments[0].get("name") if departments else None,
        employment_type=employment,
        workplace=workplace(place),
        description=html_to_text(item.get("content"), escaped=True),
    )
