"""Pinpoint (careers sites at {company}.pinpointhq.com).

    GET https://{company}.pinpointhq.com/postings.json
    {"data": [{"id", "title", "url", "workplace_type", "employment_type_text",
               "location": {"city", "province", "name"}, "job": {"department": {"name"}},
               "compensation_minimum", "compensation_maximum", "compensation_currency",
               "compensation_frequency", "compensation_visible", "description", ...}]}

Locations have no country field; the name carries it ("Calgary, Canada",
"Remote U.S."). No posting date.
"""

from __future__ import annotations

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, format_salary, html_to_text, join_text, workplace

API = "https://{slug}.pinpointhq.com/postings.json"


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url))
    items = data.get("data") or []
    return FetchResult(jobs=[_job(i, board.company_canadian) for i in items], total=len(items))


def _job(item: dict, canadian: bool) -> RawJob:
    place = item.get("location") or {}
    kind = workplace(item.get("workplace_type"))
    location = from_parts(place.get("city"), place.get("province"), None, remote=kind == "remote",
                          raw=place.get("name") or "", canadian_company=canadian)
    shown = item.get("compensation_visible")
    low, high = (item.get("compensation_minimum"), item.get("compensation_maximum")) if shown else (None, None)
    currency = item.get("compensation_currency") if shown else None
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("title")),
        url=item.get("url") or "",
        locations=[location],
        department=((item.get("job") or {}).get("department") or {}).get("name"),
        employment_type=item.get("employment_type_text"),
        workplace=kind,
        salary_text=format_salary(low, high, currency, item.get("compensation_frequency")) if shown else None,
        salary_min=low,
        salary_max=high,
        currency=currency,
        description=join_text(*(html_to_text(item.get(k)) for k in
                                 ("description", "key_responsibilities", "skills_knowledge_expertise", "benefits"))),
    )
