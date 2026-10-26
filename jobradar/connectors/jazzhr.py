"""JazzHR (careers pages at {company}.applytojob.com).

JazzHR publishes each company's open jobs as an XML feed for job sites:

    GET https://app.jazz.co/feeds/export/jobs/{company}
    <jobs><company>Xello</company>
      <job><id>job_20261005204030_…</id><status>Open</status><title>…</title>
           <department>…</department><url>…</url><city>…</city><state>ON</state>
           <country>Canada</country><description>HTML</description><type>Full Time</type></job>

An unknown company answers 404. There is no date field, but the id starts
with when the job was created (job_YYYYMMDDhhmmss_…). Some companies put
"Remote – Canada & United States" in the city field.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..http import FetchError, HttpClient
from ..locations import from_parts, normalize_country
from ..models import Board, RawJob
from ._common import FetchContext, FetchResult, clean_title, html_to_text, workplace

FEED = "https://app.jazz.co/feeds/export/jobs/{slug}"
_CREATED = re.compile(r"^job_(\d{4})(\d{2})(\d{2})")
_REMOTE = re.compile(r"\bremote\b\s*[-–—/:,]?\s*", re.I)


async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult:
    text = await client.get_text(FEED.format(slug=board.slug_or_url))
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise FetchError("the JazzHR job feed isn't valid XML") from exc
    if root.tag != "jobs":
        raise FetchError("not a JazzHR job feed")
    items = [j for j in root.findall("job") if (j.findtext("status") or "Open").strip().lower() == "open"]
    return FetchResult(jobs=[_job(j, board.company_canadian) for j in items], total=len(items))


def _location(city: str, state: str, country: str, canadian: bool):
    remote = bool(_REMOTE.search(city))
    if remote:
        # "Remote/Toronto" keeps Toronto; "Remote – Canada & United States" keeps nothing.
        city = _REMOTE.sub("", city).strip(" -–—/,")
        if "&" in city or " and " in city.lower() or normalize_country(city):
            city = ""
    return from_parts(city or None, state or None, country or None, remote=remote,
                      raw=", ".join(p for p in (city, state, country) if p), canadian_company=canadian)


def _job(item: ET.Element, canadian: bool) -> RawJob:
    text = lambda tag: (item.findtext(tag) or "").strip()  # noqa: E731
    job_id = text("id")
    created = _CREATED.match(job_id)
    location = _location(text("city"), text("state"), text("country"), canadian)
    return RawJob(
        external_id=job_id or text("url"),
        title=clean_title(text("title")),
        url=text("url"),
        locations=[location],
        posted_at="-".join(created.groups()) if created else None,
        department=text("department") or None,
        employment_type=text("type") or None,
        workplace=workplace(None, location.remote),
        description=html_to_text(item.findtext("description")),
    )
