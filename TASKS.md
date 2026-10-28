# Build plan: Job Radar

Five phases. Each one ends with something you can run and check. Read
[`PROJECT.md`](PROJECT.md) first; it is the specification.

## Ground rules for the coding agent

- Do **one phase at a time**, then stop for the human to test.
- Write the code **and** pytest tests for it. Run `pytest` and get it green
  before calling a phase done.
- Tests use recorded responses only (`tests/fixtures/`, `httpx.MockTransport`).
  No network in tests. Tests write only to temporary directories.
- Do not install packages, run live scans against real sites, or start
  long-running servers without asking. Put those steps in the phase's
  "Your manual checks" list instead.
- **The agent installs and builds nothing.** No `pip install`, no
  `npm install`, no `npm run build`. Add dependencies to `pyproject.toml` or
  `frontend/package.json` and put the install/build commands in the phase's
  "Your manual checks"; the human runs them after the phase.
- When the human installs: Python packages only into `.venv`, JavaScript
  packages only into `frontend/node_modules`. Never `sudo`,
  `pip install --user`, the system `pip`, `--break-system-packages`, `apt`,
  `snap`, `pipx`, `npm -g`, or `curl ... | sh` installers.
- Commit locally with conventional commits after each task group. No remote.
- If something in `PROJECT.md` turns out wrong, say so, write a decision
  record in `docs/decisions/`, and update the spec.

Setup the human runs once (also in `README.md` after phase 1):

```bash
cd ~/Desktop/ai_projects/job-radar
python3 -m venv .venv          # or reuse the existing one
. .venv/bin/activate
pip install -e ".[dev]"
```

---

## Phase 1: Foundation (models, locations, database, CLI skeleton) ✅ done 2026-10-26

**Goal:** the package installs, the database is created, and the location
parser handles every Canadian form we know of. No network yet.

**Tasks**
1. Project files: `pyproject.toml` (from `docs/research/draft-code/`, add
   `jinja2`, `python-multipart`), `config.toml`, `config.local.example.toml`,
   update `.gitignore` (`config.local.toml`, `data/`), `README.md` with setup
   and commands.
2. `jobradar/config.py`: load `config.toml`, merge `config.local.toml` if
   present, typed settings object with defaults.
3. `jobradar/models.py`: `Location`, `RawJob`, `Board`, size-band helper.
4. `jobradar/locations.py`: parser for all forms in
   `docs/04-canadian-sources.md` (structured fields first, then text);
   province names/codes in English and French; Canadian city list; ambiguous
   city rule; multi-location split; `is_canadian(job, company_canadian)`.
5. `jobradar/db.py`: schema from PROJECT.md §10 as migration 1, connection
   helper (WAL mode, foreign keys on), FTS5 table and triggers, basic
   query functions (upsert company/board, list companies).
6. `seeds/companies.toml`: the companies from `docs/05-seed-companies.md`.
   Possible slug collisions (vector, maple, float, fable, sonder, rewind,
   lightspeed, uber) go in with `confirmed = false`.
7. `jobradar/cli.py`: `jobradar init-db`, `jobradar seed`,
   `jobradar companies` (prints the list).
8. Copy `docs/research/samples/*.json` to `tests/fixtures/`.

**Tests**
- Location parser: one test per form in doc 04 (at least 40 cases), including
  ambiguous cities and French names.
- Database: migrations run on an empty file; upserts are idempotent; FTS finds
  inserted rows.
- Seed import: running it twice doesn't duplicate companies.

**Your manual checks**
- `pip install -e ".[dev]"` succeeds; `pytest` passes.
- `jobradar init-db && jobradar seed && jobradar companies` lists about 50
  companies.
- Open `data/jobradar.db` in any SQLite viewer (optional) and look at the
  tables.

**Commits:** `chore: scaffold package`, `feat(locations): ...`,
`feat(db): ...`, `feat(cli): ...`

---

## Phase 2: Connectors and scanning ✅ done 2026-10-26

**Goal:** `jobradar scan` pulls real jobs from every seeded company, stores
Canadian ones, and tracks open/closed over time. CSV export works.

**Tasks**
1. `jobradar/http.py`: shared async client, user agent from config, per-host
   semaphore (2), pause between pages, timeout, one retry on network
   errors/5xx.
2. Connectors, each `async fetch(board, client) -> FetchResult(jobs, total)`:
   Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Breezy,
   Rippling, BambooHR, Workday (strategy in PROJECT.md §6). Each turns its
   source into `RawJob` with parsed locations, posted date, salary,
   workplace type and plain-text description (HTML stripped with the
   standard library).
3. `jobradar/scan.py`: scan all enabled boards (or one company), isolate
   errors per board, upsert jobs, set `first_seen`/`last_seen`, set and clear
   `closed_at` (only after a successful board scan), record `scans` and
   `scan_results`, update `boards.total_open`.
4. `jobradar/export.py` + `jobradar export --out jobs.csv [--query ...]
   [--province ON,BC]`.
5. CLI: `jobradar scan [--company NAME]`, `jobradar search "query"` (prints
   top matches, handy before the UI exists).
6. Confirm Rippling's page parameter and Workday's Canada facet against the
   recorded fixtures; record any surprises in `docs/decisions/`.

**Tests**
- Each connector parses its fixture into the expected `RawJob`s (titles, ids,
  locations, dates, salary).
- Error handling: 404, 422, 302-to-homepage (BambooHR), timeout, invalid
  JSON each produce a board error, not a crash.
- Workday: facet lookup, paging stops at total, detail cap respected.
- Scan lifecycle: new job → stored; missing on next successful scan →
  closed; back again → reopened; failed scan → nothing closed.
- Non-Canadian jobs are counted in `total_open` but not stored.

**Your manual checks**
- `jobradar scan` against the real sources finishes in a few minutes, with a
  summary of boards OK/failed and jobs new/closed.
- `jobradar search "machine learning"` and `jobradar search "data analyst"`
  return sensible Canadian jobs.
- Run the scan again: few or no "new" jobs, nothing wrongly closed.
- `jobradar export --out ~/jobs.csv` opens in a spreadsheet.
- Report any board that failed, so its slug or site name can be fixed.

**Commits:** `feat(http): ...`, `feat(connectors): add greenhouse`, ... ,
`feat(scan): ...`, `feat(export): ...`

---

## Phase 3: Web UI and tracking ✅ done 2026-10-26 (checked by the user while using it)

**Goal:** everything you need day to day, in the browser: search, filters,
statuses, notes, companies, Scan now.

**Tasks**
1. **API** (`jobradar/web/app.py`): FastAPI JSON endpoints under `/api` for
   jobs (search + filters + paging), one job, status/notes updates,
   companies, one company, size/status/notes updates, boards (add, enable,
   confirm), saved searches, scans (start, progress, history), CSV export,
   and "last visit". Serves the built UI from `jobradar/web/static/` for every
   other path; a clear page if the UI isn't built yet.
   `jobradar serve [--dev] [--port]` starts Uvicorn on 127.0.0.1:8000;
   `--dev` also runs `npm run watch` in `frontend/` as a child process.
   Remove the unused `jinja2` and `python-multipart` dependencies.
2. **UI scaffold** (`frontend/`): Vite + React + TypeScript, build output to
   `../jobradar/web/static`, typed API client (`api.ts`, `types.ts`) mirroring
   the API, routing, layout, plain CSS (light and dark).
   *Later (2026-10-27):* dim and dark themes with a switch, Tailwind,
   Motion and other UI libraries; see
   `docs/decisions/2026-10-27-ui-themes-and-motion.md`.
3. **Jobs page:** keyword search (FTS5, "title only" switch), filters
   (province multi-select + Remote Canada-wide, size band, company, job
   status, company status with ignored hidden, posted within N days, job
   system, workplace, has salary), sortable results, pagination, "new since
   last visit" marker, closed label.
4. **Tracking:** inline status change and notes; `applied_at` set
   automatically, editable; `status_changed_at`.
5. **Job detail page:** description, locations, links (job page, careers
   page, LinkedIn search link built per `docs/02-linkedin-mcp-evaluation.md`).
6. **Companies page and company detail:** Canadian vs total open roles, size
   band, boards and last scan result, status, notes, **manual employee-count
   entry**, enable/disable and confirm a board (unconfirmed boards flagged).
7. **Add company** form (name, Canadian yes/no, system, slug or Workday URL).
8. **Scan now:** runs the scan in a background thread, the UI polls for
   progress; **Scans** page with per-board errors and notes.
9. **Saved searches:** save the current query + filters under a name; mark
   which ones feed Workday/Adzuna searches.
10. CSV export of the current filtered view.

**Tests** (pytest, API only; the agent can't build or run the UI)
- FastAPI `TestClient`: every endpoint on an empty and a seeded database.
- Filters: province, size band, status, ignored companies, date window each
  narrow results correctly.
- Status changes persist; `applied_at` set on first `applied`.
- "New since last visit" logic.
- Export of a filtered view contains only those rows.

**Your manual checks**
- Install and build:
  ```bash
  .venv/bin/pip install -e ".[dev]"
  cd frontend && npm install && npm run build && cd ..
  .venv/bin/pytest
  ```
- `.venv/bin/jobradar serve`, open http://127.0.0.1:8000.
- Search "ai engineer", filter to Ontario, then to "Remote (Canada-wide)".
- Mark a few jobs saved/applied with notes; restart the server; they're
  still there.
- Enter employee counts for 3 companies; filter by size band.
- Mark a company ignored; its jobs disappear from the default view.
- Click Scan now; watch progress; check the Scans page.
- Note anything awkward in the UI for phase 5.

**Commits:** `feat(web): ...` per page, `feat(tracking): ...`

---

## Phase 4: Discovering companies and company size ✅ mostly done (task 5 open)

**Split in two (2026-10-26):** part 1 is built: sizes (tasks 7 and 8),
stillhiring.today candidates, detection (task 2), the Candidates page (task 3)
and add company by careers link (task 4). Part 2 waits for an Adzuna key:
Adzuna (task 1), add job by URL (task 5), deduplication (task 6).

**Update (2026-10-26):** Adzuna's free tier is only 25 test calls, and the
user won't pay, so tasks 1 and 6 are dropped. The test calls were used once
for a snapshot (`docs/decisions/2026-10-26-adzuna-snapshot.md`). Added
instead, outside the plan: SAP SuccessFactors, JazzHR, Pinpoint, Teamtailor
and Humi connectors, and importing the user's own company lists. Task 5
(add a single job by URL) is still open.

**Also done in phase 4, outside the plan (2026-10-26 and 27):**
- **Role filtering:** `roles.toml` hides roles outside software, data and AI
  (`docs/decisions/2026-10-26-role-keywords.md`).
- **Full descriptions** for wanted roles on every system that has them
  (`docs/decisions/2026-10-26-job-descriptions.md`).
- **The Adzuna snapshot is retired automatically:** a complete scan of a
  company's confirmed board merges or closes its Adzuna copies
  (`jobradar/snapshots.py`; replaces task 6, deduplication).
- **HiBob connector** (16 job systems in all).
- **Board review and cleanup:** 215 companies remain, each with a confirmed
  board; 244 without a readable board were moved to an archive
  (`docs/decisions/2026-10-27-company-cleanup.md`).
- **Company sizes are saved as they're found** (estimates first, Wikidata in
  batches of 20), so a stopped run keeps its results.

**Goal:** the company list grows beyond the seed list, and most companies get
a size without manual entry.

~~**Before this phase (you):** sign up for an Adzuna developer key.~~ Dropped
(see the update above).

**Tasks**
1. ~~Dropped.~~ `connectors/adzuna.py`: Canada search per saved search term (and province
   when filtered), `max_days_old`, paging; store results as jobs on an
   "Adzuna" pseudo-board per company; `top_companies` per term to suggest
   companies.
2. `jobradar/detect.py`: find the job system from a careers URL or its HTML
   (host patterns in `docs/03-data-sources.md` §5), and from Adzuna redirect
   URLs. Slug probe across systems (port of `docs/research/scripts/probe.py`)
   with a **collision check** (does the board's company name or job locations
   fit?).
3. **Candidates page:** companies suggested by Adzuna or detection, with the
   detected board, a match confidence, and Approve / Reject. Nothing is added
   without your approval.
4. Add company by careers URL (detected automatically, confirm before saving).
5. **Add job by URL** for companies on systems with no feed (Dayforce, iCIMS,
   Taleo): known ATS URL → fetch; otherwise a short manual form.
6. ~~Dropped~~ (replaced by `snapshots.py`). **Deduplication:** an Adzuna job that matches a feed job (same company,
   similar title, same province, or same apply URL) is linked and hidden
   behind the feed job.
7. **stillhiring.today source** (`docs/decisions/2026-10-26-stillhiring-source.md`):
   `jobradar/sources/stillhiring.py` reads the shared Airtable view (two
   requests, at most daily), keeps Canadian-HQ rows by default (opt-in for
   others with a supported Jobs Page), maps Jobs Page → board via detection,
   Employees → company size; results go to the Candidates page with
   new / still listed / no longer listed. `jobradar candidates refresh`
   command and a button. Test from a trimmed recorded response.
8. `jobradar/enrich.py`: Wikidata SPARQL lookup of employee count (P1128) by
   company name/website, with a confirmation step for uncertain matches;
   estimate from job system + open roles when nothing else exists; manual
   always wins. `jobradar enrich` command and a button per company.

**Tests**
- Adzuna fixture parsing (record one real response once you have a key);
  missing key → clear message, no crash.
- Detection: each host pattern; HTML with an embedded board; Adzuna redirect.
- Collision check rejects a board whose jobs are all outside Canada and
  whose company name differs.
- Dedupe matching cases (positive and negative).
- Wikidata response parsing; size precedence manual > wikidata > estimate.

**Your manual checks**
- Run a scan with Adzuna on: new companies appear on the Candidates page.
- Approve a few; scan them; their jobs appear.
- Add a company by careers URL (try Scotiabank and TELUS to find their real
  Workday site names).
- Run `jobradar enrich`; check sizes for well-known companies (TD, Shopify,
  Cohere) look right.
- Confirm no duplicate jobs between Adzuna and company feeds.

**Commits:** `feat(adzuna): ...`, `feat(detect): ...`, `feat(enrich): ...`,
`feat(dedupe): ...`

---

## Phase 5: Polish and hardening (end of version 1)

**Goal:** comfortable for daily use, safe to keep data in.

**Progress (2026-10-27):** task 1 is under way. Screenshot-driven UI fixes:
page width, sidebar wrapping, the province heat map. Task 6 is partly done:
README and decision records are up to date. Tasks 2–5 and 7 are open.
Possible extra work: connectors for iCIMS / Avature / Oracle Cloud (see
`docs/decisions/2026-10-27-company-cleanup.md`).

**Added 2026-10-28: experience level and years asked** ✅ built, awaiting
your checks.
- Rules for every wanted job: a level from the title (intern, entry, mid,
  senior, lead+), and the years of experience the description states (the
  largest number; ranges from their start; company history and perks
  skipped). The level falls back to the years when the title has none.
- Jobs page: Experience and "Years of experience asked" filters (under 3,
  3–5, more than 5, not stated), a Level column, the level and years on the
  job page, two CSV columns.
- Optional Ollama step, only on request (`jobradar levels --ai`, or "Ask ..."
  under Experience): reads postings the rules left without a level or years,
  fills only what's missing, always picks a level, gives years only when
  stated, reads each job once. Gemma (`gemma4:31b-cloud`) is the default
  after a 20-job comparison with Nemotron.
- Schema versions 6 and 7. Decision record:
  `docs/decisions/2026-10-28-experience-level.md`.

Manual checks:
- `cd frontend && npm run build`, then restart `jobradar serve` (the
  database upgrades itself and works out the levels).
- Filter by Experience and by years; hover a level; open a job.
- Click "Ask gemma4:31b-cloud" (about 600 jobs, one at a time). If the free
  usage limit stops it, run it again later: answers so far are kept.
- Spot-check ten jobs against their postings.

**Tasks**
1. Fix the UI issues you noted in phases 3–4.
2. Company page: open-roles history from `scan_results` (simple table or a
   small inline SVG chart; no JS chart library).
3. `jobradar backup` (copies the SQLite file with a timestamp) and a backup
   reminder on the Scans page.
4. Board health: boards failing 3 scans in a row are flagged; one click to
   disable or edit.
5. Performance check with a full database (thousands of jobs): searches under
   a second; add indexes if needed.
6. README: full usage guide; `docs/decisions/` up to date.
7. Write the plan for version 2 (candidates: scheduled scans with a systemd
   timer, daily digest, Job Bank CSV, Jooble, MCP server for Claude, local
   LLM fit scores, hand-off to `agentic_workday`).

**Tests**
- Backup produces a valid database copy.
- Board health counter and flagging.
- History query returns per-scan counts in order.

**Your manual checks**
- Use it for a few days of real job hunting; list anything missing.
- Restore from a backup into a fresh folder and open it.

**Commits:** `fix(web): ...`, `feat(backup): ...`, `docs: ...`
