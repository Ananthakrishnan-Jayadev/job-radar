"""Read-side queries shared by the web API, the CLI and CSV export.

Every job query keeps strictly to Canada: a job shows only if it has a
Canadian location, or nothing but bare "Remote" locations (see
locations.is_canadian), whatever happens to be stored.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .levels import LEVELS, UNKNOWN_LEVEL
from .models import SIZE_BANDS, UNKNOWN_SIZE, Location

REMOTE_CANADA = "REMOTE"  # province-filter value for remote jobs open across Canada

_IN_CANADA = """
    (EXISTS (SELECT 1 FROM job_locations l WHERE l.job_id = {job} AND l.country = 'CA')
     OR (EXISTS (SELECT 1 FROM job_locations l WHERE l.job_id = {job})
         AND NOT EXISTS (SELECT 1 FROM job_locations l WHERE l.job_id = {job}
                         AND (l.remote = 0 OR l.city IS NOT NULL OR l.province IS NOT NULL
                              OR l.country IS NOT NULL))))
"""

SORTS = {
    "posted": "COALESCE(j.posted_at, substr(j.first_seen, 1, 10))",
    "first_seen": "j.first_seen",
    "title": "j.title COLLATE NOCASE",
    "company": "c.name COLLATE NOCASE",
    "status": "j.status",
}


@dataclass
class JobFilter:
    """Everything the jobs list can be narrowed by. Empty lists mean "any"."""

    query: str | None = None  # FTS5: words, "phrases", OR, prefix*
    title_only: bool = False
    provinces: list[str] = field(default_factory=list)  # codes and/or REMOTE_CANADA
    size_bands: list[str] = field(default_factory=list)  # SIZE_BANDS labels and/or "unknown"
    company_ids: list[int] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    company_statuses: list[str] = field(default_factory=list)
    include_ignored: bool = False  # jobs of companies marked "ignored"
    posted_within_days: int | None = None
    systems: list[str] = field(default_factory=list)
    workplaces: list[str] = field(default_factory=list)
    has_salary: bool = False
    include_closed: bool = False
    new_since: str | None = None  # ISO time: only jobs first seen after it
    all_roles: bool = False  # False: only roles wanted in roles.toml (tracked jobs always show)
    role_categories: list[str] = field(default_factory=list)  # software / data / ai / adjacent
    levels: list[str] = field(default_factory=list)  # levels.LEVELS and/or "unknown"


def _fts_query(f: JobFilter) -> str | None:
    if not f.query or not f.query.strip():
        return None
    return f"title : ({f.query})" if f.title_only else f.query


def _where(f: JobFilter) -> tuple[list[str], list, bool]:
    """WHERE clauses and parameters, and whether the FTS table is joined."""
    where, params = [_IN_CANADA.format(job="j.id")], []
    fts = _fts_query(f)
    if fts:
        where.append("jobs_fts MATCH ?")
        params.append(fts)
    if not f.include_closed:
        where.append("j.closed_at IS NULL")
    if f.provinces:
        codes = [p.upper() for p in f.provinces if p.upper() != REMOTE_CANADA]
        place = []
        if codes:
            place.append(f"(l.country = 'CA' AND l.province IN ({_marks(codes)}))")
            params += codes
        if len(codes) < len(f.provinces):
            place.append("(l.remote = 1 AND l.province IS NULL AND l.city IS NULL "
                         "AND COALESCE(l.country, 'CA') = 'CA')")
        where.append(f"EXISTS (SELECT 1 FROM job_locations l WHERE l.job_id = j.id AND ({' OR '.join(place)}))")
    if f.size_bands:
        bands = []
        for label, low, high in SIZE_BANDS:
            if label in f.size_bands:
                bands.append("(c.employee_count BETWEEN ? AND ?)" if high is not None else "(c.employee_count >= ?)")
                params += [low, high] if high is not None else [low]
        if UNKNOWN_SIZE in f.size_bands:
            bands.append("c.employee_count IS NULL")
        where.append(f"({' OR '.join(bands) or '0'})")
    for column, values in (("c.id", f.company_ids), ("j.status", f.statuses), ("c.status", f.company_statuses),
                           ("b.system", f.systems), ("j.workplace", f.workplaces)):
        if values:
            where.append(f"{column} IN ({_marks(values)})")
            params += list(values)
    if not f.include_ignored and "ignored" not in f.company_statuses:
        where.append("c.status != 'ignored'")
    if f.posted_within_days is not None:
        where.append(f"{SORTS['posted']} >= date('now', ?)")
        params.append(f"-{int(f.posted_within_days)} days")
    if f.has_salary:
        where.append("j.salary_text IS NOT NULL")
    if f.new_since:
        where.append("j.first_seen > ?")
        params.append(f.new_since)
    if f.levels:
        known = [lv for lv in f.levels if lv in LEVELS]
        parts = [f"j.experience_level IN ({_marks(known)})"] if known else []
        params += known
        if UNKNOWN_LEVEL in f.levels:
            parts.append("j.experience_level IS NULL")
        where.append(f"({' OR '.join(parts) or '0'})")
    if f.role_categories:
        where.append("(" + " OR ".join("j.role_categories LIKE ?" for _ in f.role_categories) + ")")
        params += [f"%,{c},%" for c in f.role_categories]
    elif not f.all_roles:
        # Unknown roles (no roles.toml, or not worked out yet) and anything the
        # user is tracking always show.
        where.append("(j.role_wanted IS NULL OR j.role_wanted = 1 OR j.status != 'new')")
    return where, params, fts is not None


def _marks(values) -> str:
    return ", ".join("?" * len(values))


_JOB_COLUMNS = """
    j.id, j.board_id, j.external_id, j.title, j.url, j.department, j.employment_type, j.workplace,
    j.posted_at, j.salary_text, j.salary_min, j.salary_max, j.currency, j.first_seen, j.last_seen,
    j.closed_at, j.status, j.notes, j.applied_at, j.status_changed_at, j.role_categories,
    j.experience_level, j.min_years, j.level_source,
    c.id AS company_id, c.name AS company, c.employee_count, c.status AS company_status,
    b.system, b.confirmed AS board_confirmed
"""


def search_jobs(
    conn: sqlite3.Connection,
    f: JobFilter,
    *,
    sort: str | None = None,
    descending: bool = True,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """(total matching, one page of jobs with their locations).

    Default order: relevance with a query, newest first without.
    """
    where, params, joined_fts = _where(f)
    base = ["FROM jobs j JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id"]
    if joined_fts:
        base.append("JOIN jobs_fts ON jobs_fts.rowid = j.id")
    base.append("WHERE " + " AND ".join(where))
    base_sql = "\n".join(base)

    total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]

    if sort in SORTS:
        order = f"{SORTS[sort]} {'DESC' if descending else 'ASC'}, j.id DESC"
    elif joined_fts:
        order = "jobs_fts.rank"
    else:
        order = f"{SORTS['posted']} DESC, j.id DESC"
    sql = f"SELECT {_JOB_COLUMNS} {base_sql} ORDER BY {order}"
    page_params = list(params)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        page_params += [limit, offset]
    rows = [dict(r) for r in conn.execute(sql, page_params).fetchall()]
    attach_locations(conn, rows)
    return total, rows


def province_counts(conn: sqlite3.Connection, f: JobFilter) -> dict[str, int]:
    """Open jobs per province (and REMOTE_CANADA) for a filter, ignoring its own province choice.

    A job listed in two provinces counts in both.
    """
    from dataclasses import replace

    where, params, joined_fts = _where(replace(f, provinces=[]))
    joins = "JOIN boards b ON b.id = j.board_id JOIN companies c ON c.id = b.company_id"
    if joined_fts:
        joins += " JOIN jobs_fts ON jobs_fts.rowid = j.id"
    conditions = " AND ".join(where)
    counts = {row[0]: row[1] for row in conn.execute(
        f"""
        SELECT place.province, COUNT(DISTINCT j.id)
        FROM jobs j {joins} JOIN job_locations place ON place.job_id = j.id
        WHERE {conditions} AND place.country = 'CA' AND place.province IS NOT NULL
        GROUP BY place.province
        """,
        params,
    )}
    counts[REMOTE_CANADA] = conn.execute(
        f"""
        SELECT COUNT(*) FROM jobs j {joins}
        WHERE {conditions} AND EXISTS (
            SELECT 1 FROM job_locations l WHERE l.job_id = j.id AND l.remote = 1 AND l.province IS NULL
            AND l.city IS NULL AND COALESCE(l.country, 'CA') = 'CA')
        """,
        params,
    ).fetchone()[0]
    return counts


def systems_in_use(conn: sqlite3.Connection) -> list[str]:
    """Job systems that have at least one open Canadian job (for the filter)."""
    rows = conn.execute(f"""
        SELECT DISTINCT b.system FROM jobs j JOIN boards b ON b.id = j.board_id
        WHERE j.closed_at IS NULL AND {_IN_CANADA.format(job='j.id')}
        ORDER BY b.system
    """)
    return [r[0] for r in rows]


def find_jobs(
    conn: sqlite3.Connection,
    query: str | None = None,
    *,
    provinces: list[str] | None = None,
    include_closed: bool = False,
    limit: int | None = None,
    all_roles: bool = False,
) -> list[dict]:
    """Shorthand used by the CLI: a query and provinces, all matches."""
    f = JobFilter(query=query, provinces=provinces or [], include_closed=include_closed, include_ignored=True,
                  all_roles=all_roles)
    return search_jobs(conn, f, limit=limit)[1]


def attach_locations(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Add a "locations" list of Location to each job row, in one query per 500 jobs."""
    if not rows:
        return
    ids = [r["id"] for r in rows]
    found: dict[int, list[Location]] = {i: [] for i in ids}
    for start in range(0, len(ids), 500):
        part = ids[start:start + 500]
        for l in conn.execute(f"SELECT * FROM job_locations WHERE job_id IN ({_marks(part)}) ORDER BY id", part):
            found[l["job_id"]].append(Location(l["city"], l["province"], l["country"], bool(l["remote"]), l["raw"]))
    for row in rows:
        row["locations"] = found[row["id"]]


def location_label(locations: list[Location]) -> str:
    """The Canadian places only: "Toronto, ON; Remote (Canada)".

    Places outside Canada are counted, not named: "Toronto, ON (+3 outside Canada)".
    """
    canadian = [l for l in locations if l.in_canada]
    if not canadian:
        bare = [l for l in locations if l.remote and not (l.city or l.province or l.country)]
        return "Remote (country not stated)" if bare else "Unknown"
    label = "; ".join(dict.fromkeys(l.label() for l in canadian))
    elsewhere = len({(l.city, l.province, l.country) for l in locations if not l.in_canada
                     and (l.city or l.province or l.country)})
    return f"{label} (+{elsewhere} outside Canada)" if elsewhere else label


def provinces_of(locations: list[Location]) -> list[str]:
    return sorted({l.province for l in locations if l.in_canada and l.province})


# --- companies ---------------------------------------------------------------------

def list_companies(
    conn: sqlite3.Connection,
    *,
    query: str | None = None,
    size_bands: list[str] | None = None,
    statuses: list[str] | None = None,
    company_id: int | None = None,
) -> list[dict]:
    """Companies with open Canadian roles, total open roles and their boards."""
    where, params = [], []
    if query and query.strip():
        where.append("c.name LIKE ?")
        params.append(f"%{query.strip()}%")
    if statuses:
        where.append(f"c.status IN ({_marks(statuses)})")
        params += statuses
    if size_bands:
        bands = []
        for label, low, high in SIZE_BANDS:
            if label in size_bands:
                bands.append("(c.employee_count BETWEEN ? AND ?)" if high is not None else "(c.employee_count >= ?)")
                params += [low, high] if high is not None else [low]
        if UNKNOWN_SIZE in size_bands:
            bands.append("c.employee_count IS NULL")
        where.append(f"({' OR '.join(bands) or '0'})")
    if company_id is not None:
        where.append("c.id = ?")
        params.append(company_id)
    sql = f"""
        SELECT c.*,
               (SELECT COUNT(*) FROM jobs j JOIN boards b ON b.id = j.board_id
                WHERE b.company_id = c.id AND j.closed_at IS NULL AND {_IN_CANADA.format(job='j.id')}) AS canada_open,
               (SELECT COUNT(*) FROM jobs j JOIN boards b ON b.id = j.board_id
                WHERE b.company_id = c.id AND j.closed_at IS NULL AND {_IN_CANADA.format(job='j.id')}
                AND (j.role_wanted IS NULL OR j.role_wanted = 1)) AS wanted_open,
               (SELECT SUM(b.total_open) FROM boards b WHERE b.company_id = c.id AND b.enabled = 1) AS total_open
        FROM companies c
        {"WHERE " + " AND ".join(where) if where else ""}
        ORDER BY c.name COLLATE NOCASE
    """
    companies = [dict(r) for r in conn.execute(sql, params).fetchall()]
    boards: dict[int, list[dict]] = {c["id"]: [] for c in companies}
    for b in conn.execute("SELECT * FROM boards ORDER BY system, slug_or_url"):
        if b["company_id"] in boards:
            boards[b["company_id"]].append(dict(b))
    for c in companies:
        c["boards"] = boards[c["id"]]
    return companies


def scan_history(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))]


def scan_results(conn: sqlite3.Connection, scan_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """
        SELECT r.*, b.system, b.slug_or_url, c.id AS company_id, c.name AS company
        FROM scan_results r JOIN boards b ON b.id = r.board_id JOIN companies c ON c.id = b.company_id
        WHERE r.scan_id = ?
        ORDER BY r.ok, c.name COLLATE NOCASE
        """,
        (scan_id,),
    )]
