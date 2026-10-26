from __future__ import annotations

from dataclasses import dataclass, field


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

    def label(self) -> str:
        parts = [p for p in (self.city, self.province) if p]
        if self.country and self.country != "CA":
            parts.append(self.country)
        text = ", ".join(parts) or (self.raw.strip() or "Unknown")
        if self.remote and "remote" not in text.lower():
            text = f"Remote ({text})" if parts else "Remote"
        return text


@dataclass
class Job:
    """One posting, normalized from whichever source it came from."""

    source: str  # "greenhouse", "workday", ...
    external_id: str  # id unique within (source, company)
    title: str
    url: str
    locations: list[Location] = field(default_factory=list)
    posted_at: str | None = None  # ISO date (YYYY-MM-DD) when known
    department: str | None = None
    salary: str | None = None
    company_name: str | None = None  # set by aggregators; feeds know their company

    def best_location(self, scope: str) -> Location | None:
        """The first location that falls inside *scope*, or None."""
        for loc in self.locations:
            if in_scope(loc, scope):
                return loc
        return None


def in_scope(loc: Location, scope: str) -> bool:
    """Ontario scope keeps Ontario jobs and remote jobs open across Canada."""
    if scope == "canada":
        return loc.in_canada
    return loc.in_ontario or (loc.in_canada and loc.remote and loc.province is None)
