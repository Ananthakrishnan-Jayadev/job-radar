"""Plain data types shared by connectors, the scanner and the database."""

from __future__ import annotations

from dataclasses import dataclass, field

# Job systems that have (or will have) a connector. Stored in boards.system.
SYSTEMS = (
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "workable",
    "recruitee",
    "breezy",
    "rippling",
    "bamboohr",
    "workday",
    "adzuna",
    "manual",
)

JOB_STATUSES = ("new", "saved", "applied", "interviewing", "offer", "rejected", "not_interested")
COMPANY_STATUSES = ("none", "target", "watching", "ignored")
WORKPLACES = ("remote", "hybrid", "onsite", "unknown")

# (label, lowest count, highest count or None). Used by the size filter.
SIZE_BANDS = (
    ("<50", 0, 49),
    ("50-199", 50, 199),
    ("200-999", 200, 999),
    ("1000-4999", 1000, 4999),
    ("5000+", 5000, None),
)
UNKNOWN_SIZE = "unknown"


def size_band(employee_count: int | None) -> str:
    """The band label for a head count, or "unknown"."""
    if employee_count is None or employee_count < 0:
        return UNKNOWN_SIZE
    for label, low, high in SIZE_BANDS:
        if employee_count >= low and (high is None or employee_count <= high):
            return label
    return UNKNOWN_SIZE


@dataclass
class Location:
    """Where a job is, as far as the posting says.

    Every field may be None: a posting that only says "Remote" has no country.
    """

    city: str | None = None
    province: str | None = None  # two-letter code for Canada ("ON"), raw text otherwise
    country: str | None = None  # ISO alpha-2 ("CA", "US"), None when unknown
    remote: bool = False
    raw: str = ""

    @property
    def in_canada(self) -> bool:
        return self.country == "CA"

    @property
    def in_ontario(self) -> bool:
        return self.country == "CA" and self.province == "ON"

    @property
    def remote_canada_wide(self) -> bool:
        """Remote anywhere in Canada: the "Remote (Canada-wide)" filter."""
        return self.in_canada and self.remote and self.province is None

    def label(self) -> str:
        parts = [p for p in (self.city, self.province) if p]
        if self.country and (self.country != "CA" or not parts):
            parts.append("Canada" if self.country == "CA" else self.country)
        text = ", ".join(parts) or (self.raw.strip() or "Unknown")
        if self.remote and "remote" not in text.lower():
            text = f"Remote ({text})" if parts else "Remote"
        return text


@dataclass
class RawJob:
    """One posting as a connector returns it, already normalized."""

    external_id: str  # unique within its board
    title: str
    url: str
    locations: list[Location] = field(default_factory=list)
    posted_at: str | None = None  # ISO date (YYYY-MM-DD) when known
    department: str | None = None
    employment_type: str | None = None
    workplace: str = "unknown"  # one of WORKPLACES
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    description: str | None = None  # plain text
    company_name: str | None = None  # set by aggregators; feeds know their company
    # False when the source gave only a summary (a Workday list entry without
    # its detail page): stored locations and description are then kept.
    details_fetched: bool = True


@dataclass
class Board:
    """One company's job feed on one job system."""

    id: int
    company_id: int
    company_name: str
    company_canadian: bool
    system: str
    slug_or_url: str
    confirmed: bool = True
    enabled: bool = True
