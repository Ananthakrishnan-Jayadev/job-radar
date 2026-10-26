"""BambooHR careers list (undocumented, used gently).

GET https://{company}.bamboohr.com/careers/list
A company without BambooHR redirects to bamboohr.com: reported as not found.
Postings titled "Test" are dropped.
"""

from __future__ import annotations

import re

from ..http import HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, fill_details, html_to_text, iso_date, workplace

API = "https://{slug}.bamboohr.com/careers/list"
_TEST_TITLE = re.compile(r"^\s*test\b", re.I)


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    data = await client.get_json(API.format(slug=board.slug_or_url))
    items = [i for i in data.get("result") or [] if not _TEST_TITLE.match(i.get("jobOpeningName") or "")]
    total = (data.get("meta") or {}).get("totalCount", len(items))
    jobs = [_job(i, board) for i in items]

    async def detail(job: RawJob) -> None:
        data = await client.get_json(f"https://{board.slug_or_url}.bamboohr.com/careers/{job.external_id}/detail")
        opening = (data.get("result") or {}).get("jobOpening") or {}
        job.description = html_to_text(opening.get("description"))
        job.posted_at = iso_date(opening.get("datePosted")) or job.posted_at
        if opening.get("compensation"):
            job.salary_text = str(opening["compensation"])

    warnings = await fill_details(jobs, ctx, client, detail)
    return FetchResult(jobs=jobs, total=total, warnings=warnings)


def _job(item: dict, board: Board) -> RawJob:
    ats = item.get("atsLocation") or {}
    basic = item.get("location") or {}
    remote = bool(item.get("isRemote"))
    location = from_parts(
        ats.get("city") or basic.get("city"),
        ats.get("province") or ats.get("state") or basic.get("state"),
        ats.get("country"),
        remote=remote,
        canadian_company=board.company_canadian,
    )
    return RawJob(
        external_id=str(item["id"]),
        title=clean_title(item.get("jobOpeningName")),
        url=f"https://{board.slug_or_url}.bamboohr.com/careers/{item['id']}",
        locations=[location],
        department=item.get("departmentLabel"),
        employment_type=item.get("employmentStatusLabel"),
        workplace=workplace(None, remote),
    )
