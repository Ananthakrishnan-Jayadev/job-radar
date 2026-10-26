"""Humi (Canadian HR platform; careers pages at {company}.applytojobs.ca).

Humi has no job feed, so this reads the careers page's HTML, the most fragile
kind of reading in this app. Each job is an <article class="job-posting">:

    <a href="/talent/50826">Title</a> ... <span>hybrid</span>
    Toronto, Ontario, Canada . full-time . September 9, 2026

If Humi changes its page layout, this connector finds no jobs and says so.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

from ..http import FetchError, HttpClient
from ..locations import parse_text
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, workplace

SITE = "https://{slug}.applytojobs.ca"
_ARTICLE = re.compile(r'<article class="job-posting[^"]*">(.*?)</article>', re.S)
_LINK = re.compile(r'<a [^>]*href="(/[^"]+)"[^>]*>(.*?)</a>', re.S)
_BADGE = re.compile(r"<span[^>]*rounded-full[^>]*>\s*([^<]+?)\s*</span>")
_META = re.compile(r"<br\s*/?>\s*([^<]+?)\s*</div>", re.S)


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    site = SITE.format(slug=board.slug_or_url)
    page = await client.get_text(site + "/")
    if "job-posting" not in page and "humi" not in page.lower():
        raise FetchError(f"{site} doesn't look like a Humi careers page")
    jobs = [job for block in _ARTICLE.findall(page) if (job := _job(block, site, board.company_canadian))]
    return FetchResult(jobs=jobs, total=len(jobs))


def _job(block: str, site: str, canadian: bool) -> RawJob | None:
    link = _LINK.search(block)
    if not link:
        return None
    path, title = link.group(1), html.unescape(re.sub(r"<[^>]+>", "", link.group(2)))
    badge = _BADGE.search(block)
    meta = _META.search(block)
    # "Toronto, Ontario, Canada . full-time . September 9, 2026"
    # Separators are " . " with any whitespace (line breaks included); "St. Catharines"
    # has no space before its dot, so it stays whole.
    parts = [" ".join(html.unescape(p).split()) for p in re.split(r"\s+\.\s+", meta.group(1))] if meta else []
    place = parts[0] if parts else ""
    kind = workplace(badge.group(1)) if badge else "unknown"
    posted = None
    if len(parts) >= 3:
        try:
            posted = datetime.strptime(" ".join(parts[2].split()), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    return RawJob(
        external_id=path.rstrip("/").rsplit("/", 1)[-1],
        title=clean_title(title),
        url=site + path,
        locations=parse_text(place, canadian_company=canadian, remote=kind == "remote"),
        posted_at=posted,
        employment_type=parts[1] if len(parts) >= 2 else None,
        workplace=kind,
    )
