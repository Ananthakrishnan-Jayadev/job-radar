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
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..http import FetchError, HttpClient
from ..locations import from_parts
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
