"""HiBob careers sites ({company}.careers.hibob.com). Undocumented.

The careers page is a script app; it reads every job, description included,
from one public request:

    GET https://{company}.careers.hibob.com/api/job-ad
    {"filterGroups": {...},
     "jobAdDetails": [{"id", "title", "department", "employmentType",
                       "site" ("Toronto", "Remote", "United States"), "country" ("Canada"),
                       "workspaceType" ("Hybrid", "On site", "Remote"), "publishedAt",
                       "description", "requirements", "responsibilities", "benefits" (HTML),
                       "payTransparencyMinSalary", "payTransparencyMaxSalary",
                       "payTransparencySalaryCurrency", "payTransparencySalaryPayPeriod"}]}

A job's page is {site}/jobs/{id}. "site" is the company's own name for an
office, so it can be a country ("United States") or "Remote"; "country" is
always a country name.
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import (
    FetchContext, FetchResult, clean_title, format_salary, html_to_text, iso_date, join_text, workplace,
)

SITE = "https://{slug}.careers.hibob.com"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    site = SITE.format(slug=board.slug_or_url)
    data = await client.get_json(f"{site}/api/job-ad")
    items = data.get("jobAdDetails") or []
    return FetchResult(jobs=[_job(i, site, board.company_canadian) for i in items], total=len(items))


def _job(item: dict, site: str, canadian: bool) -> RawJob:
    kind = workplace(item.get("workspaceType"))
    office = item.get("site") or ""
    country = item.get("country")
    city = None if office.lower() in ("remote", (country or "").lower()) else office
    location = from_parts(city, None, country, remote=kind == "remote",
                          raw=", ".join(dict.fromkeys(p for p in (office, country) if p)),
                          canadian_company=canadian)
    low, high = item.get("payTransparencyMinSalary"), item.get("payTransparencyMaxSalary")
    currency = item.get("payTransparencySalaryCurrency")
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("title")),
        url=f"{site}/jobs/{item['id']}",
        locations=[location],
        department=item.get("department") or None,
        employment_type=item.get("employmentType") or None,
        workplace=kind,
        posted_at=iso_date(item.get("publishedAt")),
        salary_text=format_salary(low, high, currency, item.get("payTransparencySalaryPayPeriod")),
        salary_min=low,
        salary_max=high,
        currency=currency,
        description=join_text(*(html_to_text(item.get(k)) for k in
                                 ("description", "responsibilities", "requirements", "benefits"))),
    )
