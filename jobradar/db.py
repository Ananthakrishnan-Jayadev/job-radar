"""SQLite storage: schema, migrations and queries.

Schema changes are numbered migrations applied in order on connect, tracked
with PRAGMA user_version. Never edit a migration that has shipped; add one.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import Location, RawJob

MIGRATIONS: list[str] = [
    # 1: initial schema (PROJECT.md section 10)
    """
    CREATE TABLE companies (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
        canadian        INTEGER NOT NULL DEFAULT 0,
        status          TEXT NOT NULL DEFAULT 'none'
                        CHECK (status IN ('none', 'target', 'watching', 'ignored')),
        notes           TEXT NOT NULL DEFAULT '',
        careers_url     TEXT,
        employee_count  INTEGER,
        size_source     TEXT CHECK (size_source IN ('manual', 'wikidata', 'estimate')),
        size_updated_at TEXT,
        created_at      TEXT NOT NULL
    );

    CREATE TABLE boards (
        id              INTEGER PRIMARY KEY,
        company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        system          TEXT NOT NULL,
        slug_or_url     TEXT NOT NULL,
        confirmed       INTEGER NOT NULL DEFAULT 1,
        enabled         INTEGER NOT NULL DEFAULT 1,
        last_scanned_at TEXT,
        last_error      TEXT,
        total_open      INTEGER,
        UNIQUE (system, slug_or_url)
    );
    CREATE INDEX boards_company ON boards(company_id);

    CREATE TABLE jobs (
        id                INTEGER PRIMARY KEY,
        board_id          INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
        external_id       TEXT NOT NULL,
        title             TEXT NOT NULL,
        url               TEXT NOT NULL,
        department        TEXT,
        employment_type   TEXT,
        workplace         TEXT NOT NULL DEFAULT 'unknown'
                          CHECK (workplace IN ('remote', 'hybrid', 'onsite', 'unknown')),
        posted_at         TEXT,
        salary_text       TEXT,
        salary_min        REAL,
        salary_max        REAL,
        currency          TEXT,
        description       TEXT,
        first_seen        TEXT NOT NULL,
        last_seen         TEXT NOT NULL,
        closed_at         TEXT,
        status            TEXT NOT NULL DEFAULT 'new'
                          CHECK (status IN ('new', 'saved', 'applied', 'interviewing',
                                            'offer', 'rejected', 'not_interested')),
        notes             TEXT NOT NULL DEFAULT '',
        applied_at        TEXT,
        status_changed_at TEXT,
        UNIQUE (board_id, external_id)
    );
    CREATE INDEX jobs_status ON jobs(status);
    CREATE INDEX jobs_first_seen ON jobs(first_seen);
    CREATE INDEX jobs_posted_at ON jobs(posted_at);

    CREATE TABLE job_locations (
        id       INTEGER PRIMARY KEY,
        job_id   INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        city     TEXT,
        province TEXT,
        country  TEXT,
        remote   INTEGER NOT NULL DEFAULT 0,
        raw      TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX job_locations_job ON job_locations(job_id);
    CREATE INDEX job_locations_place ON job_locations(country, province);

    CREATE VIRTUAL TABLE jobs_fts USING fts5(
        title, company, department, description,
        tokenize = 'unicode61 remove_diacritics 2'
    );

    CREATE TRIGGER jobs_fts_insert AFTER INSERT ON jobs BEGIN
        INSERT INTO jobs_fts (rowid, title, company, department, description)
        VALUES (
            new.id, new.title,
            (SELECT c.name FROM boards b JOIN companies c ON c.id = b.company_id
             WHERE b.id = new.board_id),
            new.department, new.description
        );
    END;
    CREATE TRIGGER jobs_fts_update AFTER UPDATE OF title, department, description ON jobs BEGIN
        UPDATE jobs_fts
        SET title = new.title, department = new.department, description = new.description
        WHERE rowid = new.id;
    END;
    CREATE TRIGGER jobs_fts_delete AFTER DELETE ON jobs BEGIN
        DELETE FROM jobs_fts WHERE rowid = old.id;
    END;
    CREATE TRIGGER companies_fts_rename AFTER UPDATE OF name ON companies BEGIN
        UPDATE jobs_fts SET company = new.name
        WHERE rowid IN (SELECT j.id FROM jobs j JOIN boards b ON b.id = j.board_id
                        WHERE b.company_id = new.id);
    END;

    CREATE TABLE scans (
        id            INTEGER PRIMARY KEY,
        started_at    TEXT NOT NULL,
        finished_at   TEXT,
        boards_ok     INTEGER NOT NULL DEFAULT 0,
        boards_failed INTEGER NOT NULL DEFAULT 0,
        jobs_new      INTEGER NOT NULL DEFAULT 0,
        jobs_closed   INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE scan_results (
        id          INTEGER PRIMARY KEY,
        scan_id     INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        board_id    INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
        ok          INTEGER NOT NULL,
        jobs_seen   INTEGER NOT NULL DEFAULT 0,
        jobs_canada INTEGER NOT NULL DEFAULT 0,
        error       TEXT,
        ms          INTEGER
    );
    CREATE INDEX scan_results_board ON scan_results(board_id);

    CREATE TABLE saved_searches (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL UNIQUE,
        query           TEXT NOT NULL DEFAULT '',
        filters         TEXT NOT NULL DEFAULT '{}',
        use_for_sources INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    );
    """,
    # 2: history of status changes, shown on the job page
    """
    CREATE TABLE job_events (
        id     INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        at     TEXT NOT NULL,
        field  TEXT NOT NULL,
        old    TEXT,
        new    TEXT
    );
    CREATE INDEX job_events_job ON job_events(job_id);
    """,
    # 3: company size from stillhiring.today, HQ and website, size suggestions;
    #    listings of candidate companies. SQLite can't change a CHECK in place,
    #    so companies is rebuilt (the documented create-copy-drop-rename way).
    """
    DROP TRIGGER jobs_fts_insert;
    CREATE TABLE companies_new (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
        canadian        INTEGER NOT NULL DEFAULT 0,
        status          TEXT NOT NULL DEFAULT 'none'
                        CHECK (status IN ('none', 'target', 'watching', 'ignored')),
        notes           TEXT NOT NULL DEFAULT '',
        careers_url     TEXT,
        website         TEXT,
        hq_city         TEXT,
        hq_province     TEXT,
        hq_country      TEXT,
        employee_count  INTEGER,
        size_source     TEXT CHECK (size_source IN ('manual', 'stillhiring', 'wikidata', 'estimate')),
        size_updated_at TEXT,
        size_suggestion TEXT,
        wikidata_id     TEXT,
        created_at      TEXT NOT NULL
    );
    INSERT INTO companies_new (id, name, canadian, status, notes, careers_url, employee_count,
                               size_source, size_updated_at, created_at)
    SELECT id, name, canadian, status, notes, careers_url, employee_count,
           size_source, size_updated_at, created_at
    FROM companies;
    DROP TABLE companies;
    ALTER TABLE companies_new RENAME TO companies;

    CREATE TRIGGER jobs_fts_insert AFTER INSERT ON jobs BEGIN
        INSERT INTO jobs_fts (rowid, title, company, department, description)
        VALUES (
            new.id, new.title,
            (SELECT c.name FROM boards b JOIN companies c ON c.id = b.company_id
             WHERE b.id = new.board_id),
            new.department, new.description
        );
    END;
    CREATE TRIGGER companies_fts_rename AFTER UPDATE OF name ON companies BEGIN
        UPDATE jobs_fts SET company = new.name
        WHERE rowid IN (SELECT j.id FROM jobs j JOIN boards b ON b.id = j.board_id
                        WHERE b.company_id = new.id);
    END;

    CREATE TABLE listings (
        id              INTEGER PRIMARY KEY,
        source          TEXT NOT NULL,
        external_id     TEXT NOT NULL,
        name            TEXT NOT NULL,
        tagline         TEXT,
        employees       INTEGER,
        hq_country      TEXT,
        hq_province     TEXT,
        hq_city         TEXT,
        jobs_url        TEXT,
        detected_system TEXT,
        detected_slug   TEXT,
        detect_note     TEXT,
        company_id      INTEGER REFERENCES companies(id) ON DELETE SET NULL,
        decision        TEXT NOT NULL DEFAULT 'pending'
                        CHECK (decision IN ('pending', 'approved', 'rejected')),
        first_seen      TEXT NOT NULL,
        last_seen       TEXT NOT NULL,
        gone_at         TEXT,
        UNIQUE (source, external_id)
    );
    CREATE INDEX listings_decision ON listings(decision);
    """,
    # 4: size_source loses its CHECK list (sources are validated in enrich.PRIORITY),
    #    so adding a source ("imported", from the user's own lists) needs no rebuild again.
    """
    DROP TRIGGER jobs_fts_insert;
    CREATE TABLE companies_new (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
        canadian        INTEGER NOT NULL DEFAULT 0,
        status          TEXT NOT NULL DEFAULT 'none'
                        CHECK (status IN ('none', 'target', 'watching', 'ignored')),
        notes           TEXT NOT NULL DEFAULT '',
        careers_url     TEXT,
        website         TEXT,
        hq_city         TEXT,
        hq_province     TEXT,
        hq_country      TEXT,
        employee_count  INTEGER,
        size_source     TEXT,
        size_updated_at TEXT,
        size_suggestion TEXT,
        wikidata_id     TEXT,
        created_at      TEXT NOT NULL
    );
    INSERT INTO companies_new SELECT id, name, canadian, status, notes, careers_url, website, hq_city,
        hq_province, hq_country, employee_count, size_source, size_updated_at, size_suggestion,
        wikidata_id, created_at FROM companies;
    DROP TABLE companies;
    ALTER TABLE companies_new RENAME TO companies;

    CREATE TRIGGER jobs_fts_insert AFTER INSERT ON jobs BEGIN
        INSERT INTO jobs_fts (rowid, title, company, department, description)
        VALUES (
            new.id, new.title,
            (SELECT c.name FROM boards b JOIN companies c ON c.id = b.company_id
             WHERE b.id = new.board_id),
            new.department, new.description
        );
    END;
    CREATE TRIGGER companies_fts_rename AFTER UPDATE OF name ON companies BEGIN
        UPDATE jobs_fts SET company = new.name
        WHERE rowid IN (SELECT j.id FROM jobs j JOIN boards b ON b.id = j.board_id
                        WHERE b.company_id = new.id);
    END;
    """,
    # 5: each job's role categories from roles.toml (",software,data," or ""),
    #    and whether they include an enabled one. NULL = not worked out yet.
    """
    ALTER TABLE jobs ADD COLUMN role_categories TEXT;
    ALTER TABLE jobs ADD COLUMN role_wanted INTEGER;
    CREATE INDEX jobs_role_wanted ON jobs(role_wanted);
    """,
    # 6: experience level (intern / entry / mid / senior / lead), the years the
    #    description asks for, and where the level came from (see levels.py).
    #    A changed title or description is worked out again.
    """
    ALTER TABLE jobs ADD COLUMN experience_level TEXT;
    ALTER TABLE jobs ADD COLUMN min_years INTEGER;
    ALTER TABLE jobs ADD COLUMN level_source TEXT;
    CREATE INDEX jobs_level_todo ON jobs(id) WHERE level_source IS NULL;
    CREATE INDEX jobs_level ON jobs(experience_level);
    CREATE TRIGGER jobs_level_reset AFTER UPDATE OF title, description ON jobs
    WHEN old.title IS NOT new.title OR old.description IS NOT new.description BEGIN
        UPDATE jobs SET experience_level = NULL, min_years = NULL, level_source = NULL WHERE id = new.id;
    END;
    """,
    # 7: which model was asked about a job's level and years (levels.py), so
    #    it's asked once; a changed title or description clears it.
    """
    ALTER TABLE jobs ADD COLUMN level_asked TEXT;
    UPDATE jobs SET level_asked = substr(level_source, 8) WHERE level_source LIKE 'ollama:%';
    DROP TRIGGER jobs_level_reset;
    CREATE TRIGGER jobs_level_reset AFTER UPDATE OF title, description ON jobs
    WHEN old.title IS NOT new.title OR old.description IS NOT new.description BEGIN
        UPDATE jobs SET experience_level = NULL, min_years = NULL, level_source = NULL, level_asked = NULL
        WHERE id = new.id;
    END;
    """,
]


def now() -> str:
    """Current UTC time as ISO text, the format stored everywhere."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) the database and bring the schema up to date."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # timeout: wait if a background scan is writing.
    # check_same_thread=False: the web app may open a request's connection on one
    # worker thread and close it on another. Each connection still serves one
    # request (or one background task) at a time; it is never shared.
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns the new schema version."""
    version = schema_version(conn)
    for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
        # Foreign keys are off while a migration rebuilds tables, and checked after.
        conn.execute("PRAGMA foreign_keys = OFF")
        # One transaction per migration: it applies completely or not at all.
        conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.execute("PRAGMA foreign_keys = ON")
        if problems:
            raise RuntimeError(f"migration {number} broke foreign keys: {problems[:5]}")
    return schema_version(conn)


# --- companies and boards ---------------------------------------------------------

def upsert_company(
    conn: sqlite3.Connection,
    name: str,
    *,
    canadian: bool | None = None,
    careers_url: str | None = None,
) -> int:
    """Insert a company or update the given fields. Status and notes are kept."""
    row = conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
    with conn:
        if row is None:
            cur = conn.execute(
                "INSERT INTO companies (name, canadian, careers_url, created_at) VALUES (?, ?, ?, ?)",
                (name, int(bool(canadian)), careers_url, now()),
            )
            return cur.lastrowid
        if canadian is not None:
            conn.execute("UPDATE companies SET canadian = ? WHERE id = ?", (int(canadian), row["id"]))
        if careers_url is not None:
            conn.execute("UPDATE companies SET careers_url = ? WHERE id = ?", (careers_url, row["id"]))
    return row["id"]


def upsert_board(
    conn: sqlite3.Connection,
    company_id: int,
    system: str,
    slug_or_url: str,
    *,
    confirmed: bool = True,
    enabled: bool | None = None,
) -> int:
    """Insert a board or return the existing one.

    Re-adding a board never un-confirms it: once confirmed, it stays confirmed.
    *enabled* None leaves an existing board as it is (new boards are enabled).
    """
    with conn:
        conn.execute(
            """
            INSERT INTO boards (company_id, system, slug_or_url, confirmed, enabled)
            VALUES (?, ?, ?, ?, COALESCE(?, 1))
            ON CONFLICT (system, slug_or_url) DO UPDATE
            SET confirmed = MAX(boards.confirmed, excluded.confirmed),
                enabled = COALESCE(?, boards.enabled)
            """,
            (company_id, system, slug_or_url, int(confirmed),
             None if enabled is None else int(enabled), None if enabled is None else int(enabled)),
        )
    row = conn.execute(
        "SELECT id FROM boards WHERE system = ? AND slug_or_url = ?", (system, slug_or_url)
    ).fetchone()
    return row["id"]


def list_companies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Companies with their boards summarized, sorted by name."""
    return conn.execute(
        """
        SELECT c.*,
               COUNT(b.id) AS board_count,
               GROUP_CONCAT(b.system || ':' || b.slug_or_url
                            || CASE WHEN b.confirmed THEN '' ELSE ' (unconfirmed)' END
                            || CASE WHEN b.enabled THEN '' ELSE ' (disabled)' END, ', ') AS boards,
               SUM(b.total_open) AS total_open
        FROM companies c LEFT JOIN boards b ON b.company_id = c.id
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE
        """
    ).fetchall()


# --- jobs --------------------------------------------------------------------------

def upsert_job(
    conn: sqlite3.Connection, board_id: int, job: RawJob, seen_at: str | None = None
) -> tuple[int, bool]:
    """Store a job seen in a scan. Returns (job id, whether it is new).

    Source fields are refreshed; tracking fields (status, notes, applied_at) and
    first_seen are never touched. A job seen again is reopened.
    """
    seen_at = seen_at or now()
    existing = conn.execute(
        "SELECT id FROM jobs WHERE board_id = ? AND external_id = ?", (board_id, job.external_id)
    ).fetchone()
    values = (
        job.title, job.url, job.department, job.employment_type, job.workplace,
        job.posted_at, job.salary_text, job.salary_min, job.salary_max, job.currency,
        job.description,
    )
    with conn:
        if existing is None:
            cur = conn.execute(
                """
                INSERT INTO jobs (title, url, department, employment_type, workplace,
                                  posted_at, salary_text, salary_min, salary_max, currency,
                                  description, board_id, external_id, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values, board_id, job.external_id, seen_at, seen_at),
            )
            job_id, is_new = cur.lastrowid, True
        else:
            job_id, is_new = existing["id"], False
            conn.execute(
                """
                UPDATE jobs SET title = ?, url = ?, department = ?, employment_type = ?,
                                workplace = ?, posted_at = COALESCE(?, posted_at),
                                salary_text = ?, salary_min = ?, salary_max = ?, currency = ?,
                                description = COALESCE(?, description),
                                last_seen = ?, closed_at = NULL
                WHERE id = ?
                """,
                (*values, seen_at, job_id),
            )
        if is_new or job.details_fetched or not job_locations(conn, job_id):
            _replace_locations(conn, job_id, job.locations)
    return job_id, is_new


def _replace_locations(conn: sqlite3.Connection, job_id: int, locations: list[Location]) -> None:
    conn.execute("DELETE FROM job_locations WHERE job_id = ?", (job_id,))
    conn.executemany(
        "INSERT INTO job_locations (job_id, city, province, country, remote, raw) VALUES (?, ?, ?, ?, ?, ?)",
        [(job_id, l.city, l.province, l.country, int(l.remote), l.raw) for l in locations],
    )


def job_locations(conn: sqlite3.Connection, job_id: int) -> list[Location]:
    rows = conn.execute(
        "SELECT city, province, country, remote, raw FROM job_locations WHERE job_id = ? ORDER BY id",
        (job_id,),
    ).fetchall()
    return [Location(r["city"], r["province"], r["country"], bool(r["remote"]), r["raw"]) for r in rows]


def search_jobs(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[sqlite3.Row]:
    """Full-text search over title, company, department and description.

    *query* uses FTS5 syntax: words, "exact phrases", OR, prefix*.
    """
    return conn.execute(
        """
        SELECT j.*, c.name AS company
        FROM jobs_fts f
        JOIN jobs j ON j.id = f.rowid
        JOIN boards b ON b.id = j.board_id
        JOIN companies c ON c.id = b.company_id
        WHERE jobs_fts MATCH ?
        ORDER BY f.rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()


# --- settings ----------------------------------------------------------------------

def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return default if row is None else json.loads(row["value"])


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    with conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
