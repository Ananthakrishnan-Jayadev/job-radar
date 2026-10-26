"""Workday careers sites (undocumented JSON behind the public careers page).

Board slug is the careers-site URL: https://{tenant}.wd{N}.myworkdayjobs.com/{site}

    POST https://{host}/wday/cxs/{tenant}/{site}/jobs
         {"appliedFacets": {...}, "limit": 20, "offset": N, "searchText": "..."}
    GET  https://{host}/wday/cxs/{tenant}/{site}{externalPath}   (one job)

Strategy (PROJECT.md section 6):
1. Offset 0, no filter: total open jobs and the id of the Canada country facet.
2. Filtered to Canada: list everything if at most workday.max_list jobs,
   otherwise search per saved-search term (a partial read: nothing is closed).
3. Fetch the detail page (exact date, all locations, description) only for
   jobs not already stored with details, at most workday.max_details_per_scan.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..http import FetchError, HttpClient
from ..locations import parse_text, with_country
from ..models import Board, Location, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, html_to_text, iso_date, relative_date, workplace

PAGE = 20  # Workday rejects larger pages
_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_MULTI = re.compile(r"^\s*\d+\s+locations?\s*$", re.I)


def parse_site(url: str) -> tuple[str, str, str]:
    """(host, tenant, site) from a careers-site URL."""
    parts = urlsplit(url)
    if not parts.netloc.endswith("myworkdayjobs.com"):
        raise FetchError(f"not a Workday careers URL: {url}")
    segments = [s for s in parts.path.split("/") if s]
    if segments and _LOCALE.match(segments[0]):
        segments = segments[1:]
    if not segments:
        raise FetchError(f"Workday URL has no site name: {url}")
    return parts.netloc, parts.netloc.split(".")[0], segments[0]


def find_country_facet(facets: list, country: str = "Canada") -> tuple[str, str] | None:
    """(facet parameter, value id) for *country*, searching nested facet groups."""
    for facet in facets or []:
        param = facet.get("facetParameter") or ""
        for value in facet.get("values") or []:
            if "values" in value:  # a group such as locationMainGroup
                found = find_country_facet([value], country)
                if found:
                    return found
            elif "country" in param.lower() and (value.get("descriptor") or "").lower() == country.lower():
                return param, value["id"]
    return None


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    host, tenant, site = parse_site(board.slug_or_url)
    api = f"https://{host}/wday/cxs/{tenant}/{site}"
    settings = ctx.settings.workday
    delay = settings.delay_seconds

    first = await client.post_json(f"{api}/jobs", _body({}, 0, ""))
    total = first.get("total") or 0
    facet = find_country_facet(first.get("facets") or [])
    if facet is None:
        return FetchResult(jobs=[], total=total, warnings=["no Canada location facet: no Canadian jobs listed"])
    applied = {facet[0]: [facet[1]]}

    await client.pause(delay)
    canada = await client.post_json(f"{api}/jobs", _body(applied, 0, ""))
    canada_total = canada.get("total") or 0
    warnings: list[str] = []

    if canada_total <= settings.max_list:
        postings = await _page_all(client, api, applied, "", canada, settings.max_list, delay)
        complete = len(postings) >= canada_total
    elif ctx.search_terms:
        postings, seen = [], set()
        for term in ctx.search_terms:
            await client.pause(delay)
            for p in await _page_all(client, api, applied, term, None, settings.max_list, delay):
                if p["externalPath"] not in seen:
                    seen.add(p["externalPath"])
                    postings.append(p)
        complete = False
        warnings.append(f"{canada_total} Canadian jobs, over the {settings.max_list} limit: "
                        f"searched {len(ctx.search_terms)} terms instead")
    else:
        postings = await _page_all(client, api, applied, "", canada, settings.max_list, delay)
        complete = False
        warnings.append(f"{canada_total} Canadian jobs, read the first {len(postings)}; "
                        "add search terms to cover the rest")

    jobs = [_from_list(p, host, site, board, ctx) for p in postings]
    details_done = 0
    for job, posting in zip(jobs, postings):
        if job.external_id in ctx.known_ids or details_done >= settings.max_details_per_scan:
            continue
        await client.pause(delay)
        try:
            detail = await client.get_json(f"{api}{posting['externalPath']}")
        except FetchError as exc:
            warnings.append(f"detail for {job.external_id} failed: {exc}")
            continue
        _apply_detail(job, detail, board)
        details_done += 1
    pending = sum(1 for j in jobs if not j.details_fetched and j.external_id not in ctx.known_ids)
    if pending:
        warnings.append(f"{pending} job details left for the next scan")
    return FetchResult(jobs=jobs, total=total, complete=complete, warnings=warnings)


def _body(applied: dict, offset: int, search: str) -> dict:
    return {"appliedFacets": applied, "limit": PAGE, "offset": offset, "searchText": search}


async def _page_all(client, api, applied, search, first_page, cap, delay) -> list[dict]:
    """All postings for one filter, up to *cap*. Reuses an already fetched first page."""
    page = first_page or await client.post_json(f"{api}/jobs", _body(applied, 0, search))
    total = page.get("total") or 0  # only reliable on the first page
    postings = [p for p in page.get("jobPostings") or [] if p.get("externalPath")]
    offset = PAGE
    while offset < min(total, cap):
        await client.pause(delay)
        page = await client.post_json(f"{api}/jobs", _body(applied, offset, search))
        batch = [p for p in page.get("jobPostings") or [] if p.get("externalPath")]
        if not batch:
            break
        postings += batch
        offset += PAGE
    return postings[:cap]


def _canada(locations: list[Location], canadian: bool) -> list[Location]:
    """The facet guarantees Canada; fill it in where the text didn't say."""
    return [with_country(loc, "CA", canadian_company=canadian) for loc in locations]


def _from_list(posting: dict, host: str, site: str, board: Board, ctx: FetchContext) -> RawJob:
    path = posting["externalPath"]
    text = posting.get("locationsText") or ""
    canadian = board.company_canadian
    if text and not _MULTI.match(text):
        locations = parse_text(text, canadian_company=canadian)
    else:
        # "/job/Toronto-Ontario/Data-Scientist_JR00128241" names the first location.
        segments = path.split("/")
        locations = parse_text(segments[2], canadian_company=canadian) if len(segments) > 3 else []
    locations = _canada(locations, canadian) or [Location(country="CA", raw=text)]
    return RawJob(
        external_id=path.rsplit("/", 1)[-1],
        title=clean_title(posting.get("title")),
        url=f"https://{host}/{site}{path}",
        locations=locations,
        posted_at=relative_date(posting.get("postedOn"), ctx.today),
        details_fetched=False,
    )


def _apply_detail(job: RawJob, detail: dict, board: Board) -> None:
    info = detail.get("jobPostingInfo") or {}
    canadian = board.company_canadian
    remote_type = info.get("remoteType") or ""
    remote = "remote" in remote_type.lower()
    places = [info.get("location"), *(info.get("additionalLocations") or [])]
    locations = []
    for place in filter(None, places):
        locations += parse_text(place, canadian_company=canadian, remote=remote)
    country = (info.get("country") or {}).get("descriptor")
    locations = [with_country(l, country, canadian_company=canadian) for l in locations]
    if locations:
        job.locations = dedupe_locations(locations)
    job.title = clean_title(info.get("title")) or job.title
    job.url = info.get("externalUrl") or job.url
    job.posted_at = iso_date(info.get("startDate")) or job.posted_at
    job.employment_type = info.get("timeType")
    job.workplace = workplace(remote_type)
    job.description = html_to_text(info.get("jobDescription"))
    job.details_fetched = True
