# Job Radar: project specification

A personal, local tool that collects Canadian job postings from public company
job feeds and job-search APIs, lets you search them freely, filter by province
and company size, and track what you've saved and applied to.

Research behind every decision here is in [`docs/`](docs/00-START-HERE.md).
The build is split into phases in [`TASKS.md`](TASKS.md). Decisions are
recorded in [`docs/decisions/`](docs/decisions/).

---

## 1. Goals

1. **Find jobs** in Canada from many companies at once, without LinkedIn.
2. **Search them freely.** Any keywords ("ai engineer", "data analyst",
   "python", "dbt"), not a fixed list of roles.
3. **Filter** by province (or remote across Canada), company size, company,
   status, date posted, and job system.
4. **See companies, not only jobs:** how many Canadian roles each one has open,
   how many in total, and how big it is.
5. **Track** jobs and companies by hand ("box them in"): statuses, notes, date
   applied. Tracking survives the posting disappearing.

## 2. Non-goals (version 1)

- Applying to jobs or filling in forms (`agentic_workday` does that; a hand-off
  may come later).
- Multi-user use, login, hosting, deployment.
- LinkedIn automation of any kind. Plain "open this search on LinkedIn" links
  are allowed.
- Filtering by work authorization.
- Scheduled scans. Scans run on demand (button or command) in version 1.
- Notifications, LLM summaries and fit scores (later phase, after v1).

## 3. Users and environment

- One user, on their own Linux machine.
- Python 3.11+ (the machine has 3.14), `pip` + `venv`.
- Runs at `http://127.0.0.1:8000`. No authentication: it only listens on
  localhost.

## 4. Stack

| Part | Choice | Why |
|---|---|---|
| Language | **Python** for everything except the UI | User's choice |
| Web API | FastAPI + Uvicorn, JSON under `/api` | Same as the user's other projects |
| UI | **React + TypeScript**, built with Vite into `jobradar/web/static/` and served by FastAPI | User's choice; one server, one terminal |
| HTTP | httpx (async), per-host concurrency limit and pause | Gentle on sources |
| Storage | SQLite through the standard `sqlite3` module, FTS5 for search | One file, no server, full-text search built in |
| Config | TOML (`config.toml`, read with `tomllib`) | No extra package; draft already in TOML |
| Secrets | `config.local.toml` (git-ignored) | API keys for Adzuna etc. |
| Command line | `argparse`, entry point `jobradar` | No extra package |
| Tests | pytest, recorded responses as fixtures, `httpx.MockTransport` | No network in tests |

Python runtime dependencies: `fastapi`, `uvicorn[standard]`, `httpx`.
Dev: `pytest`. UI dependencies (in `frontend/package.json`): `react`,
`react-dom`, `react-router-dom`; dev: `vite`, `@vitejs/plugin-react`,
`typescript`, `@types/react`, `@types/react-dom`. No UI component or state
libraries: plain CSS and React state are enough for one user.

**One terminal.** `jobradar serve` runs Uvicorn, which serves both the API and
the built UI at http://127.0.0.1:8000. The UI is built once with
`npm run build` (in `frontend/`). `jobradar serve --dev` also starts
`vite build --watch` as a child process, so UI edits rebuild on save, still
in one terminal; it stops when the server stops.

## 5. Architecture

```
            ┌──────────────┐   ┌───────────────────────┐
 seeds/ ──► │  companies   │◄──│ discovery (phase 4):   │
 UI add ──► │  + boards    │   │ Adzuna, detect job     │
            └──────┬───────┘   │ system, slug probe     │
                   │           └───────────────────────┘
                   ▼
            ┌──────────────┐   one connector per job system,
            │  scan engine │──► same interface:
            └──────┬───────┘   fetch(board, client) -> list[RawJob]
                   ▼
            ┌──────────────┐
            │  normalize   │   location parser (country/province/remote),
            │              │   dates, salary text, plain-text description
            └──────┬───────┘
                   ▼
            ┌──────────────┐   upsert by (board, external_id);
            │  store       │   first_seen / last_seen / closed_at;
            │  (SQLite)    │   per-scan counts and errors
            └──────┬───────┘
                   ▼
     ┌─────────────┴─────────────┐
     ▼                           ▼
  web UI (search, filters,    CLI (scan, export CSV,
  tracking, scan now)         seed, serve)
```

### Package layout

```
job-radar/
  pyproject.toml
  config.toml               # settings, safe to commit
  config.local.toml         # API keys (git-ignored), example in config.local.example.toml
  seeds/companies.toml      # starting company list
  jobradar/
    __init__.py
    config.py               # load config.toml + config.local.toml
    models.py               # Location, RawJob, Board dataclasses
    locations.py            # location parser
    db.py                   # schema, migrations (PRAGMA user_version), queries
    scan.py                 # scan engine
    http.py                 # shared httpx client, per-host limits, user agent
    connectors/
      __init__.py           # registry: system name -> connector
      greenhouse.py lever.py ashby.py smartrecruiters.py workable.py
      recruitee.py breezy.py rippling.py bamboohr.py workday.py successfactors.py jazzhr.py
      pinpoint.py teamtailor.py humi.py
      adzuna.py             # phase 4
    detect.py               # job-system detection from URLs/HTML (phase 4)
    enrich.py               # company size (phase 4)
    export.py               # CSV
    cli.py
    web/
      app.py                # FastAPI app: /api routes + serves the built UI
      scanner.py            # background "Scan now" (own thread and DB connection)
      static/               # built UI from frontend/ (git-ignored, generated)
  frontend/                 # React + TypeScript source (Vite)
    package.json  vite.config.ts  tsconfig.json  index.html
    src/
      main.tsx  App.tsx  api.ts  types.ts  styles.css
      pages/                # Jobs, JobDetail, Companies, CompanyDetail, Scans, Settings
      components/           # Filters, JobTable, StatusSelect, ...
  tests/
    fixtures/               # recorded responses (from docs/research/samples)
    test_*.py
  data/                     # jobradar.db lives here (git-ignored)
```

## 6. Data sources in version 1

Per-company feeds (details and field lists in `docs/03-data-sources.md`):

| System | Endpoint | Notes |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | One request, all jobs |
| Lever | `api.lever.co/v0/postings/{company}?mode=json` | `createdAt` in ms; salaryRange |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true` | Structured address; skip `isListed=false` |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{id}/postings` | Paged by 100; drop very old postings (configurable max age) |
| Workable | `apply.workable.com/api/v1/widget/accounts/{sub}` | |
| Recruitee | `{c}.recruitee.com/api/offers/` | Salary |
| Breezy HR | `{c}.breezy.hr/json` | |
| Rippling | `ats.rippling.com/api/v2/board/{c}/jobs` | Paged by 20; page param to confirm in phase 2 |
| BambooHR | `{c}.bamboohr.com/careers/list` | Undocumented; 302 to bamboohr.com = not found; drop titles like "Test" |
| Workday | `POST {host}/wday/cxs/{tenant}/{site}/jobs` | Undocumented; 20 per page; Canada facet; see below |
| SAP SuccessFactors | `{site}/sitemap.xml` (an RSS feed of every job) | Added 2026-10-26 for Scotiabank; one large request; no posting date |
| JazzHR | `app.jazz.co/feeds/export/jobs/{company}` (XML) | Added 2026-10-26; careers pages at `{company}.applytojob.com`; date from the job id |
| Pinpoint | `{company}.pinpointhq.com/postings.json` | Added 2026-10-26; salary when shown; no posting date |
| Teamtailor | `{site}/jobs.rss` | Added 2026-10-26; board is the site address (`*.teamtailor.com` or own domain) |
| Humi | `{company}.applytojobs.ca` (HTML) | Added 2026-10-26; no feed, reads the careers page: the most fragile connector |

Added in phase 4: **Adzuna** (Canada search, `top_companies`) and **Wikidata**
(employee counts).

### Workday strategy

Workday lists can be large (TD: 1,126 jobs worldwide), and the list has no
description. Per board:

1. First request (offset 0) reads the `Location_Country` facet and finds the id
   for Canada. Later requests filter with that facet.
2. If the Canadian total is at or below `workday.max_list` (default 400), list
   them all. Otherwise run one search per **saved search** term instead.
3. Fetch the job detail (exact date, all locations, description) only for jobs
   seen for the first time, at most `workday.max_details_per_scan` (default 60)
   per board per scan; the rest are filled in on later scans.
4. Pause `workday.delay_seconds` (default 1.0) between requests.

## 7. Search, filters and the location rule

**Which jobs are stored.** A job is stored if any of its locations is in
Canada, or it is remote with no country given **and** the company is marked
Canadian. Everything else is counted (for "total open roles") but not stored.

**Location parser** (`jobradar/locations.py`) turns each source's location
data into `Location(city, province, country, remote, raw)`:
- Uses structured fields first (Ashby address, Lever `country`,
  SmartRecruiters/Recruitee/Workable/Rippling/BambooHR country and region).
- Falls back to text: "Toronto, ON", "Toronto, Ontario, Canada",
  "TORONTO-Ontario-Canada", "Remote – Canada", "Montréal, QC", French accents.
- Splits multiple places (`;` in Greenhouse, Workday `additionalLocations`).
- Knows province names and codes and a list of Canadian cities without a
  province. Ambiguous cities (London, Waterloo, Hamilton, Kingston, Windsor,
  Cambridge, Richmond) count as Canadian only when the country is Canada or the
  company is Canadian.
- Full list of forms in `docs/04-canadian-sources.md`.

**Province filter:** multi-select of the 13 provinces and territories, plus
"Remote (Canada-wide)" (remote, country Canada, no province). Default: all of
Canada.

**Keyword search:** SQLite FTS5 over title, company name, department and
description. Supports phrases (`"machine learning"`), OR, and prefix
(`analy*`). A "title only" switch limits it to the title.

**Other filters:** company size band, company, job status, company status
(ignored companies hidden by default), posted within N days, job system,
remote/hybrid/onsite where known, has salary.

**Saved searches:** named keyword + filter combinations, kept in the database
and shown as one-click views. Their keywords also drive the sources that search
on their own side (Workday over the limit, Adzuna).

## 8. Company size

- Stored per company: `employee_count` (number, optional), `size_source`
  (`manual`, `wikidata`, `estimate`), `size_updated_at`.
- **Size bands** for the filter: under 50, 50–199, 200–999, 1,000–4,999,
  5,000+, and Unknown.
- Version 1 order: manual entry (phase 3) → Wikidata P1128 (phase 4) →
  estimate from job system and open roles (phase 4, shown as "estimated").
  Manual always wins.

## 9. Tracking

**Job statuses:** `new` → `saved` → `applied` → `interviewing` → `offer` /
`rejected`, plus `not_interested`. Each job also has `notes` and `applied_at`
(set automatically when the status becomes `applied`, editable).

**Company statuses:** `none`, `target`, `watching`, `ignored`. Notes per
company. `ignored` hides all its jobs by default.

**Lifecycle:** every job keeps `first_seen`, `last_seen` and `closed_at`. A
job missing from a successful scan of its board gets `closed_at`; if it comes
back, `closed_at` is cleared. A failed scan never closes jobs. **Jobs are never
deleted.** Tracked jobs that closed stay visible with a "closed" label.

**New since last visit:** the app stores the time of your previous visit to the
jobs page; jobs first seen after it get a "new" marker.

## 10. Database (SQLite)

```
companies      id, name, canadian (bool), status, notes, careers_url,
               employee_count, size_source, size_updated_at, created_at
boards         id, company_id, system, slug_or_url, confirmed (bool),
               enabled (bool), last_scanned_at, last_error,
               total_open (all jobs worldwide at last scan)
jobs           id, board_id, external_id, title, url, department,
               employment_type, workplace (remote/hybrid/onsite/unknown),
               posted_at, salary_text, salary_min, salary_max, currency,
               description, first_seen, last_seen, closed_at,
               status, notes, applied_at, status_changed_at
               UNIQUE(board_id, external_id)
job_locations  job_id, city, province, country, remote, raw
jobs_fts       FTS5(title, company, department, description)
scans          id, started_at, finished_at, boards_ok, boards_failed,
               jobs_new, jobs_closed
scan_results   scan_id, board_id, ok, jobs_seen, jobs_canada, error, ms
saved_searches id, name, query, filters (JSON), use_for_sources (bool)
settings       key, value     (e.g. last_visit_at)
```

Schema changes go through numbered migrations applied on start
(`PRAGMA user_version`).

## 11. Scanning rules

- **On demand** in version 1: `jobradar scan` or the "Scan now" button. One
  scan at a time; the UI shows progress.
- **Isolation:** each board is scanned in its own try/except. One broken source
  is logged in `scan_results` and shown in the UI; the rest carry on.
- **Gentle:** at most 2 requests at once per host, a short pause between pages,
  timeouts of 20 s, one retry on network errors and 5xx, no retry on 4xx.
- **User agent:** `job-radar/0.1 (personal use; <contact from config>)`, with a
  browser-like fallback setting if a source rejects it.
- No login, no CAPTCHA solving, nothing behind authentication.

## 12. Web UI (version 1)

- **Jobs** (home): search box, filters, results table (title, company,
  location, size band, posted, salary, status, new marker), inline status
  change and notes, saved searches, CSV export of the current view.
- **Job detail:** description, all locations, links (job page, company
  careers page, a LinkedIn search link), status history.
- **Companies:** table with Canadian roles open, total roles open, size, job
  system(s), status, last scan result; filters by size band and status.
- **Company detail:** boards, size (editable), notes, its jobs.
- **Add company:** name + board (system + slug/URL), or (phase 4) a careers
  URL that is detected automatically.
- **Scans:** last runs, per-board errors, "Scan now".
- **Settings:** saved searches used for Workday/Adzuna, defaults.

## 13. Process rules for the coding agent

- Python is the main language. The UI is React + TypeScript in `frontend/`;
  all data logic (search, filters, tracking rules) stays in the Python API.
- **Tests:** every phase adds pytest tests. Tests never touch the network
  (`httpx.MockTransport` with fixtures from `tests/fixtures/`) and write only
  to temporary directories. The agent runs `pytest` and fixes failures before
  finishing a phase.
- **Manual testing:** every phase ends with a written checklist ("Your manual
  checks") in `TASKS.md` for the human to run: installs, live scans, clicking
  through the UI. The agent does not run live scans against real sources or
  install packages without asking.
- **The agent installs nothing.** The human runs every install (`pip` into
  `.venv`, `npm install` inside `frontend/`) and every UI build after a phase.
  Python packages only ever go into `.venv`, JavaScript packages only into
  `frontend/node_modules`; never system-wide, `--user`, `sudo`, `npm -g`, or
  other package managers. The agent lists new dependencies in
  `pyproject.toml` / `frontend/package.json` and the install commands in the
  phase's manual checks.
- **One phase at a time.** Stop at the end of each phase for the human to test.
- **Git:** local only for now. Conventional commits (`type(scope): subject`,
  imperative, under 50 characters). Commit at the end of each task group.
- **Decisions:** anything that changes this spec gets a dated record in
  `docs/decisions/` and an update here.
