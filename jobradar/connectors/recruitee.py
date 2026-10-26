"""Recruitee public careers feed.

GET https://{company}.recruitee.com/api/offers/
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import (
    FetchContext, FetchResult, clean_title, dedupe_locations, format_salary, html_to_text, iso_date, join_text,
)

API = "https://{slug}.recruitee.com/api/offers/"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url))
    offers = [o for o in data.get("offers", []) if o.get("status", "published") == "published"]
    return FetchResult(jobs=[_job(o, board.company_canadian) for o in offers], total=len(offers))


def _job(item: dict, canadian: bool) -> RawJob:
    remote = bool(item.get("remote"))
    locations = [
        from_parts(p.get("city"), p.get("state"), p.get("country_code") or p.get("country"),
                   remote=remote, canadian_company=canadian)
        for p in item.get("locations") or []
    ] or [from_parts(item.get("city"), item.get("state_name"), item.get("country_code") or item.get("country"),
                     remote=remote, canadian_company=canadian)]
    salary = item.get("salary") or {}
    kind = "remote" if remote else "hybrid" if item.get("hybrid") else "onsite" if item.get("on_site") else "unknown"
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("title")),
        url=item.get("careers_url") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("published_at") or item.get("created_at")),
        department=item.get("department"),
        employment_type=item.get("employment_type_code"),
        workplace=kind,
        salary_text=format_salary(salary.get("min"), salary.get("max"), salary.get("currency"), salary.get("period")),
        salary_min=salary.get("min"),
        salary_max=salary.get("max"),
        currency=salary.get("currency"),
        description=join_text(html_to_text(item.get("description")), html_to_text(item.get("requirements"))),
    )
