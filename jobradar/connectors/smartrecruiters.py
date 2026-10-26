"""SmartRecruiters Posting API (official, public). Paged by 100.

GET https://api.smartrecruiters.com/v1/companies/{id}/postings?limit=100&offset=N
GET .../postings/{posting id}   (one job: jobAd.sections hold the description; wanted roles only)
Postings older than smartrecruiters.max_age_days are skipped: some boards keep
postings from years ago.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, fill_details, html_to_text, iso_date, join_text, workplace

API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE = 100
MAX_PAGES = 50


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    url = API.format(slug=board.slug_or_url)
    items, total, offset = [], 0, 0
    for _ in range(MAX_PAGES):
        data = await client.get_json(url, params={"limit": PAGE, "offset": offset})
        page = data.get("content") or []
        total = data.get("totalFound", total)
        items += page
        offset += len(page)
        if not page or offset >= total:
            break
        await client.pause()

    cutoff = ((ctx.today or date.today()) - timedelta(days=ctx.settings.smartrecruiters_max_age_days)).isoformat()
    jobs = [_job(i, board) for i in items]
    fresh = [j for j in jobs if j.posted_at is None or j.posted_at >= cutoff]
    warnings = [f"skipped {len(jobs) - len(fresh)} postings older than {cutoff}"] if len(fresh) < len(jobs) else []

    async def detail(job: RawJob) -> None:
        data = await client.get_json(f"{url}/{job.external_id}")
        sections = (data.get("jobAd") or {}).get("sections") or {}
        job.description = join_text(*(html_to_text((sections.get(k) or {}).get("text"))
                                       for k in ("jobDescription", "qualifications", "additionalInformation",
                                                 "companyDescription")))

    warnings += await fill_details(fresh, ctx, client, detail)
    return FetchResult(jobs=fresh, total=total, warnings=warnings)


def _job(item: dict, board: Board) -> RawJob:
    place = item.get("location") or {}
    remote = bool(place.get("remote"))
    company = (item.get("company") or {}).get("identifier") or board.slug_or_url
    kind = "remote" if remote else "hybrid" if place.get("hybrid") else "onsite"
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("name")),
        url=f"https://jobs.smartrecruiters.com/{company}/{item['id']}",
        locations=[from_parts(place.get("city"), place.get("region"), place.get("country"),
                              remote=remote, raw=place.get("fullLocation") or "",
                              canadian_company=board.company_canadian)],
        posted_at=iso_date(item.get("releasedDate")),
        department=(item.get("department") or {}).get("label") or (item.get("function") or {}).get("label"),
        employment_type=(item.get("typeOfEmployment") or {}).get("label"),
        workplace=workplace(kind),
    )
