"""Turn what the user pastes (a slug or a careers URL) into a board slug.

Phase 4's detection builds on this; here it only understands each supported
job system's own URLs.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .connectors import CONNECTORS

# system -> (host pattern, where the slug is: "path" = first path segment, "sub" = subdomain)
_URL_FORMS = {
    "greenhouse": (r"(boards|job-boards)(\.eu)?\.greenhouse\.io$", "path"),
    "lever": (r"jobs\.(eu\.)?lever\.co$", "path"),
    "ashby": (r"jobs\.ashbyhq\.com$", "path"),
    "smartrecruiters": (r"(jobs|careers)\.smartrecruiters\.com$", "path"),
    "workable": (r"apply\.workable\.com$", "path"),
    "recruitee": (r"^([\w-]+)\.recruitee\.com$", "sub"),
    "breezy": (r"^([\w-]+)\.breezy\.hr$", "sub"),
    "rippling": (r"ats\.rippling\.com$", "path"),
    "bamboohr": (r"^([\w-]+)\.bamboohr\.com$", "sub"),
}


class BoardError(ValueError):
    pass


def normalize_board(system: str, value: str) -> str:
    """The slug (or, for Workday, the careers-site URL) to store for a board."""
    value = (value or "").strip()
    if system not in CONNECTORS:
        raise BoardError(f"unsupported job system {system!r}")
    if not value:
        raise BoardError("enter the board's slug or URL")
    if system == "workday":
        from .connectors.workday import parse_site
        from .http import FetchError

        try:
            host, _, site = parse_site(value if value.startswith("http") else f"https://{value}")
        except FetchError as exc:
            raise BoardError(str(exc)) from exc
        return f"https://{host}/{site}"
    if not re.match(r"^(https?://|[\w.-]+\.\w+/)", value):
        return value  # already a slug
    parts = urlsplit(value if value.startswith("http") else f"https://{value}")
    host = parts.netloc.lower()
    pattern, where = _URL_FORMS[system]
    match = re.search(pattern, host)
    if not match:
        raise BoardError(f"{host} is not a {system} address")
    if where == "sub":
        return match.group(1)
    segments = [s for s in parts.path.split("/") if s]
    if system == "greenhouse" and segments[:2] == ["embed", "job_board"]:
        query = dict(p.split("=", 1) for p in parts.query.split("&") if "=" in p)
        if query.get("for"):
            return query["for"]
    if system == "rippling" and segments:
        return segments[0]
    if not segments:
        raise BoardError(f"no board name in {value}")
    return segments[0]
