"""Ashby Posting API (official, public).

GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, format_salary, iso_date, workplace

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url), params={"includeCompensation": "true"})
    items = [i for i in data.get("jobs", []) if i.get("isListed", True)]
    return FetchResult(jobs=[_job(i, board.company_canadian) for i in items], total=len(items))


def _location(entry: dict, remote: bool, canadian: bool):
    address = (entry.get("address") or {}).get("postalAddress") or {}
    return from_parts(
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
        remote=remote,
        raw=entry.get("location") or "",
        canadian_company=canadian,
    )


def _job(item: dict, canadian: bool) -> RawJob:
    remote = bool(item.get("isRemote"))
    locations = [_location(item, remote, canadian)]
    for extra in item.get("secondaryLocations") or []:
        locations.append(_location(extra, remote, canadian))

    comp = item.get("compensation") or {}
    salary = next(
        (c for c in comp.get("summaryComponents") or [] if c.get("compensationType") == "Salary"), {}
    )
    salary_text = comp.get("scrapeableCompensationSalarySummary") or format_salary(
        salary.get("minValue"), salary.get("maxValue"), salary.get("currencyCode"), salary.get("interval")
    )
    return RawJob(
        external_id=item["id"],
        title=clean_title(item.get("title")),
        url=item.get("jobUrl") or "",
        locations=dedupe_locations(locations),
        posted_at=iso_date(item.get("publishedAt")),
        department=item.get("department") or item.get("team"),
        employment_type=item.get("employmentType"),
        workplace=workplace(item.get("workplaceType"), remote),
        salary_text=salary_text,
        salary_min=salary.get("minValue"),
        salary_max=salary.get("maxValue"),
        currency=salary.get("currencyCode"),
        description=item.get("descriptionPlain"),
    )
