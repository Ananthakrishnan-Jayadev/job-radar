"""stillhiring.today: a community list of tech companies that are hiring.

The list lives in a shared Airtable view. There is no official API for it, so
we read it the way the embedded page does (undocumented; accepted by the user,
see docs/decisions/2026-10-26-stillhiring-source.md):

1. GET the embed page; it carries a short-lived signed data URL and the base id.
2. GET that URL with the headers Airtable's own page sends.

Two requests per refresh. Expect it to break if Airtable changes its page.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..http import FetchError, HttpClient

SOURCE = "stillhiring"
EMBED_URL = "https://airtable.com/embed/shrI8dno1rMGKZM8y"
SITE_URL = "https://stillhiring.today/"

_DATA_URL = re.compile(r'urlWithParams:\s*"([^"]+)"')
_APP_ID = re.compile(r'"applicationId":"(app\w+)"')


@dataclass
class Listing:
    external_id: str  # Airtable row id
    name: str
    tagline: str | None
    employees: int | None
    hq_country: str | None  # ISO, e.g. "CA"
    hq_province: str | None  # "ON" from "CA-ON"
    hq_city: str | None
    jobs_url: str | None


def parse_embed_page(html: str) -> tuple[str, str]:
    """(data URL, application id) from the embed page."""
    url, app = _DATA_URL.search(html), _APP_ID.search(html)
    if not url or not app:
        raise FetchError("stillhiring: the Airtable page changed; its data link wasn't found")
    path = json.loads(f'"{url.group(1)}"')  # undo the \\u002F escapes
    return f"https://airtable.com{path}", app.group(1)


def parse_view(data: dict) -> list[Listing]:
    """Rows of the shared view as Listings, by column name (column ids may change)."""
    try:
        table = data["data"]["table"]
        columns = {c["name"]: c for c in table["columns"]}
        rows = table["rows"]
    except (KeyError, TypeError) as exc:
        raise FetchError("stillhiring: unexpected data format") from exc

    def cell(row: dict, name: str):
        column = columns.get(name)
        return row["cellValuesByColumnId"].get(column["id"]) if column else None

    out = []
    for row in rows:
        name = (cell(row, "Company Name") or "").strip()
        if not name:
            continue
        jobs = cell(row, "Jobs Page")
        state = cell(row, "HQ State") or ""
        employees = cell(row, "Employees")
        out.append(Listing(
            external_id=row["id"],
            name=name,
            tagline=cell(row, "Tagline"),
            employees=int(employees) if isinstance(employees, (int, float)) else None,
            hq_country=(cell(row, "HQ Country") or None),
            hq_province=state.split("-", 1)[1] if "-" in state else None,
            hq_city=cell(row, "HQ City"),
            jobs_url=jobs.get("url") if isinstance(jobs, dict) else None,
        ))
    return out


async def fetch_listings(client: HttpClient) -> list[Listing]:
    page = await client.get_text(EMBED_URL)
    data_url, app_id = parse_embed_page(page)
    response = await client.request(
        "GET", data_url, follow_redirects=True,
        headers={
            "x-airtable-application-id": app_id,
            "x-requested-with": "XMLHttpRequest",
            "x-time-zone": "America/Toronto",
            "x-user-locale": "en",
        },
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise FetchError("stillhiring: the data link didn't return JSON") from exc
    return parse_view(data)
