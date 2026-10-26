"""Teamtailor career sites ({company}.teamtailor.com, {company}.na.teamtailor.com,
or the company's own domain).

The board is the site's address; its RSS feed lists every open job:

    GET {site}/jobs.rss
    <item><title/><link/><guid/><pubDate/><description>HTML</description>
          <remoteStatus>fully|hybrid|temporary|none</remoteStatus>
          <tt:locations><tt:location><tt:name/><tt:city/><tt:country/></tt:location></tt:locations>
          <tt:department/></item>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..http import FetchError, HttpClient
from ..locations import from_parts
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, dedupe_locations, html_to_text

TT = "{https://teamtailor.com/locations}"
_WORKPLACE = {"fully": "remote", "hybrid": "hybrid", "temporary": "remote", "none": "onsite"}


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    site = board.slug_or_url.rstrip("/")
    text = await client.get_text(f"{site}/jobs.rss")
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise FetchError(f"{site}/jobs.rss isn't a Teamtailor job feed") from exc
    items = root.findall("./channel/item")
    return FetchResult(jobs=[_job(i, board.company_canadian) for i in items], total=len(items))


def _posted(value: str | None) -> str | None:
    try:
        return parsedate_to_datetime(value).date().isoformat() if value else None
    except (TypeError, ValueError):
        return None


def _job(item: ET.Element, canadian: bool) -> RawJob:
    kind = _WORKPLACE.get((item.findtext("remoteStatus") or "").strip().lower(), "unknown")
    locations = [
        from_parts(loc.findtext(f"{TT}city"), None, loc.findtext(f"{TT}country"), remote=kind == "remote",
                   raw=loc.findtext(f"{TT}name") or "", canadian_company=canadian)
        for loc in item.iter(f"{TT}location")
    ]
    link = (item.findtext("link") or "").strip()
    return RawJob(
        external_id=(item.findtext("guid") or link).strip(),
        title=clean_title(item.findtext("title")),
        url=link,
        locations=dedupe_locations(locations),
        posted_at=_posted(item.findtext("pubDate")),
        department=(item.findtext(f"{TT}department") or "").strip() or None,
        workplace=kind,
        description=html_to_text(item.findtext("description")),
    )
