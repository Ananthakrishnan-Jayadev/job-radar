"""Lever Postings API (official, public).

GET https://api.lever.co/v0/postings/{company}?mode=json
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import parse_text, with_country
from ..models import Board, RawJob
from ._common import (
    FetchContext, FetchResult, clean_title, dedupe_locations, format_salary, html_to_text,
    iso_date, join_text, workplace,
)

API = "https://api.lever.co/v0/postings/{slug}"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url), params={"mode": "json"})
    if not isinstance(data, list):
        data = []
    jobs = [_job(item, board.company_canadian) for item in data]
    return FetchResult(jobs=jobs, total=len(jobs))


def _job(item: dict, canadian: bool) -> RawJob:
    categories = item.get("categories") or {}
    kind = workplace(item.get("workplaceType"))
    places = categories.get("allLocations") or [categories.get("location") or ""]
    locations = []
    for place in places:
        for loc in parse_text(place, canadian_company=canadian, remote=kind == "remote"):
            locations.append(with_country(loc, item.get("country"), canadian_company=canadian))
    if not locations and item.get("country"):
        locations = parse_text(item["country"], remote=kind == "remote")

    salary = item.get("salaryRange") or {}
    lists = "\n\n".join(
        f"{block.get('text', '')}\n{html_to_text(block.get('content')) or ''}"
        for block in item.get("lists") or []
    )
    return RawJob(
        external_id=item["id"],
        title=clean_title(item.get("text")),
        url=item.get("hostedUrl") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("createdAt")),
        department=categories.get("team") or categories.get("department"),
        employment_type=categories.get("commitment"),
        workplace=kind,
        salary_text=format_salary(salary.get("min"), salary.get("max"), salary.get("currency"), salary.get("interval")),
        salary_min=salary.get("min"),
        salary_max=salary.get("max"),
        currency=salary.get("currency"),
        description=join_text(item.get("descriptionPlain"), lists, item.get("additionalPlain")),
    )
