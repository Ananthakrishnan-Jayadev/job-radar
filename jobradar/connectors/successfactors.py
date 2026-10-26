"""SAP SuccessFactors career sites ("Career Site Builder", e.g. jobs.scotiabank.com).

The board is the site's address. Its /sitemap.xml is, despite the name, an
RSS feed of every open job with Google job fields, published for search
engines:

    GET {site}/sitemap.xml
    <item><title>…</title><link>…</link><guid>id</guid>
          <g:location>Toronto, ON, CA</g:location><g:job_function>…</g:job_function>
          <description>escaped HTML</description></item>

One request reads the whole board, but it can be large (Scotiabank: 38 MB for
1,471 jobs, mostly images inside descriptions). There is no posting date, only
an expiry date, so "posted" falls back to the day we first saw a job.

Some sites (EY) publish only a plain list of links at /sitemap.xml. Those are
read from their search pages instead, filtered to Canada, 25 rows a page:

    GET {site}/search/?q=&locationsearch=Canada&startrow=N
    <span class="paginationLabel">Results <b>1 – 25</b> of <b>423</b></span>
    <tr class="data-row"> <a class="jobTitle-link" href="/ey/job/.../1449196533/">Title</a>
        <span class="jobLocation"> Montréal, Quebec, CA, H3A 0A8 </span>
        <span class="jobDate"> Oct 18, 2026 </span> </tr>

No descriptions in that mode. Sites whose search page builds its rows by
script (Teck) can't be read.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from ..http import FetchError, HttpClient
from ..locations import from_parts, parse_text
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, html_to_text

G = "{http://base.google.com/ns/1.0}"
# "Software Engineer (Toronto, ON, CA)" -> the title without its location suffix.
_LOCATION_SUFFIX = re.compile(r"\s*\([^()]*,\s*[A-Z]{2}(?:,[^()]*)?\)\s*$")
_EMBEDDED_IMAGES = re.compile(r"data:image/[^\"'&\s]+")


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    site = board.slug_or_url.rstrip("/")
    text = await client.get_text(f"{site}/sitemap.xml")
    # Drop embedded images before parsing: they are nearly all of the bytes.
    text = _EMBEDDED_IMAGES.sub("", text)
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise FetchError(f"the job feed at {site}/sitemap.xml isn't valid XML") from exc
    if root.tag.endswith("urlset"):
        return await _from_search_pages(client, site, board.company_canadian)
    if root.tag != "rss":
        raise FetchError(f"{site}/sitemap.xml isn't a SuccessFactors job feed")
    items = root.findall("./channel/item")
    jobs = [_job(item, board.company_canadian) for item in items]
    return FetchResult(jobs=[j for j in jobs if j], total=len(items))


def _job(item: ET.Element, canadian: bool) -> RawJob | None:
    job_id = item.findtext(f"{G}id") or item.findtext("guid")
    link = item.findtext("link")
    if not job_id or not link:
        return None
    place = (item.findtext(f"{G}location") or "").strip()
    parts = [p.strip() for p in place.split(",")]
    city, region, country = (parts + [None, None, None])[:3]
    location = from_parts(city, region, country, raw=place, canadian_company=canadian)
    return RawJob(
        external_id=job_id.strip(),
        title=clean_title(_LOCATION_SUFFIX.sub("", item.findtext("title") or "")),
        url=link.strip(),
        locations=[location],
        department=(item.findtext(f"{G}job_function") or "").strip() or None,
        description=html_to_text(item.findtext("description"), escaped=True),
    )


# --- search pages (sites without a job feed) -----------------------------------------

ROWS_PER_PAGE = 25
MAX_PAGES = 80
_ROW = re.compile(r'<tr class="data-row">(.*?)</tr>', re.S)
_LINK = re.compile(r'<a [^>]*href="([^"]*/job/[^"]*?/(\d+)/?)"[^>]*class="jobTitle-link"[^>]*>(.*?)</a>'
                   r'|<a [^>]*class="jobTitle-link"[^>]*href="([^"]*/job/[^"]*?/(\d+)/?)"[^>]*>(.*?)</a>', re.S)
_LOCATION = re.compile(r'<span class="jobLocation">\s*(.*?)\s*</span>', re.S)
_DATE = re.compile(r'<span class="jobDate[^"]*">\s*(.*?)\s*</span>', re.S)
_TOTAL = re.compile(r"Results <b>[^<]*</b> of <b>([\d,]+)</b>")


async def _from_search_pages(client: HttpClient, site: str, canadian: bool) -> FetchResult:
    jobs: dict[str, RawJob] = {}
    total = None
    for page in range(MAX_PAGES):
        text = await client.get_text(f"{site}/search/", params={
            "q": "", "locationsearch": "Canada", "startrow": page * ROWS_PER_PAGE})
        rows = _ROW.findall(text)
        if total is None:
            found = _TOTAL.search(text)
            if not rows and not found:
                raise FetchError(f"{site} builds its job list by script and publishes no job feed; it can't be read")
            total = int(found.group(1).replace(",", "")) if found else len(rows)
        for row in rows:
            job = _search_row(row, site, canadian)
            if job:
                jobs[job.external_id] = job
        if not rows or (page + 1) * ROWS_PER_PAGE >= total:
            break
        await client.pause()
    complete = len(jobs) >= (total or 0)
    warnings = [] if complete else [f"read {len(jobs)} of {total} Canadian jobs from the search pages"]
    return FetchResult(jobs=list(jobs.values()), total=total or 0, complete=complete, warnings=warnings)


def _search_row(row: str, site: str, canadian: bool) -> RawJob | None:
    link = _LINK.search(row)
    if not link:
        return None
    href, job_id, title = (link.group(1), link.group(2), link.group(3)) if link.group(1) else \
        (link.group(4), link.group(5), link.group(6))
    place = _LOCATION.search(row)
    date = _DATE.search(row)
    posted = None
    if date:
        try:
            posted = datetime.strptime(" ".join(date.group(1).split()), "%b %d, %Y").date().isoformat()
        except ValueError:
            pass
    location_text = html.unescape(place.group(1)) if place else ""
    return RawJob(
        external_id=job_id,
        title=clean_title(html.unescape(re.sub(r"<[^>]+>", "", title))),
        url=site + html.unescape(href) if href.startswith("/") else html.unescape(href),
        locations=parse_text(location_text, canadian_company=canadian) or [],
        posted_at=posted,
    )
