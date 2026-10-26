# Architecture draft (proposed during research, not final)

This is what was proposed in the session before the user asked to plan properly.
Treat it as input to the plan, not as the plan.

## Pipeline

```
┌─ 1. Find companies ──────────────────────────┐
│ Adzuna (ca) · Jooble · Job Bank CSV ·         │  → candidate companies and a
│ seed list (05) · manual "add company"         │    "hiring in Ontario" signal
└──────────────────────────────────────────────┘
                     ↓
┌─ 2. Detect each company's job system ────────┐
│ careers URL/HTML → greenhouse / lever / ashby │  → stored per company;
│ / workday / smartrecruiters / … / unknown;    │    the user confirms guesses
│ fallback: guess slugs (watch for collisions)  │
└──────────────────────────────────────────────┘
                     ↓
┌─ 3. One small connector per job system ──────┐  same interface for all:
│ fetch_jobs(company) → [Job]                   │  title, url, locations,
│                                               │  posted_at, department, salary
└──────────────────────────────────────────────┘
                     ↓
┌─ 4. Normalize + match + store ───────────────┐
│ location parser (Ontario / Canada / remote),  │
│ role matcher (config patterns), dedupe,       │
│ first_seen / last_seen / closed per job       │  ← daily snapshots
└──────────────────────────────────────────────┘
                     ↓
┌─ 5. Enrich ──────────────────────────────────┐
│ company size: Wikidata → PDL/Apollo → estimate│
│ → manual override; industry; HQ               │
└──────────────────────────────────────────────┘
                     ↓
┌─ 6. Rank + track + UI ───────────────────────┐
│ score = role match × Ontario roles × size fit │
│ × hiring momentum; statuses, notes, filters,  │
│ "new since last visit", CSV export            │
│ Later: MCP server so Claude can query it      │
└──────────────────────────────────────────────┘
```

## Design choices proposed

- **Scan on a schedule, not on every request.** Daily (cron or systemd timer)
  plus a "Scan now" button. It keeps us within every source's limits and builds
  history (who is ramping up hiring).
- **The location parser carries the Canada focus.** Get it right and every
  source becomes Canada-filtered. See the forms in 04.
- **Detect the job system automatically and store the result**, so detection
  runs once per company.
- **Small, isolated connectors.** When an undocumented endpoint changes, one
  connector breaks, not the app. Log and show per-company scan errors.
- **Role matching from config:** each role profile has `include` patterns,
  `exclude` patterns, and `search` terms for sources that search on their own
  side (Workday `searchText`, Adzuna `what`). Plus global excludes (director,
  VP, head of, manager...). Draft in `research/draft-code/config.toml`.
- **Two scopes:** `ontario` (Ontario plus Canada-wide remote) and `canada`.
- **A job is identified** by `(source, company, external_id)`. Keep
  `first_seen`, `last_seen`, and `closed_at` when it disappears from the feed.
  **Never delete a tracked job.**
- **Statuses** (proposal): jobs: `new → saved → applied → interviewing →
  offer / rejected`, plus `not_interested`; companies: `target`, `watching`,
  `ignored`. Notes and `applied_at` on both. LinkedIn's vocabulary for
  comparison: `easy_apply | external | applied | closed | unknown`.
- **Dedupe** the same job from an aggregator and a company feed, by normalized
  title, company and location, or by matching apply links.
- **Stack proposed:** Python 3.11+, FastAPI, httpx (async, with a limit on
  concurrent requests to the same host), SQLite (Postgres not needed for
  personal use), and a plain HTML, JavaScript and CSS front end, the same
  approach as the user's `hireflow` and `agentic_workday`. pytest with recorded
  responses (`research/samples/`) as fixtures.
- **Configuration** in TOML (Python reads it without extra packages) or YAML
  (more friendly to edit by hand, and `agentic_workday` already uses it).
  Undecided.
- **Interface options discussed:** a web dashboard (needed for "boxing in" and
  tracking), a command-line tool that writes CSVs, an MCP server for Claude.
  Suggested: core library → command line → web UI, then MCP later.
- **First end-to-end slice proposed:** Greenhouse, Lever and Ashby connectors,
  the Ontario location parser, SQLite storage, a ranked CSV. Then Workday,
  aggregators, size enrichment and the UI.

## Draft data model (from `research/draft-code/models.py`)

```python
@dataclass
class Location:
    city: str | None; province: str | None   # "ON" for Canada
    country: str | None                     # ISO alpha-2
    remote: bool; raw: str
    # in_canada, in_ontario, label()

@dataclass
class Job:
    source: str; external_id: str; title: str; url: str
    locations: list[Location]; posted_at: str | None   # YYYY-MM-DD
    department: str | None; salary: str | None
    company_name: str | None   # set by aggregators
    # best_location(scope)

def in_scope(loc, scope):  # "canada" → in_canada;
    # "ontario" → in_ontario or (in_canada and remote and province is None)
```

Tables sketched: `companies` (name, source, slug or URL, size, size_source,
status, notes, last_scanned, scan_error), `jobs` (company_id, source,
external_id, title, url, location label, ontario/canada flags, remote, role
profile, posted_at, salary, first_seen, last_seen, closed_at), `tracking`
(job_id, status, applied_at, notes), `scans` (time, counts, errors).

## Idea list for "make the experience better" (not confirmed by the user)

- "New since last visit" markers; a daily digest (email or desktop notification).
- Company page: Ontario matching roles against total, size, job system, history
  chart of open roles.
- Saved filters / views ("AI roles, Toronto, under 500 people").
- Salary column where available; filter by minimum salary.
- Quick links: the job page, the company careers page, and a LinkedIn search link
  built with the URL grammar from 02 (just a link, no automation).
- Fit notes or score per job; later an LLM summary of each description against
  the user's résumé (local Ollama, as in `agentic_workday`).
- Export to CSV; back up the SQLite file.
- Mark a whole company `ignored` to hide all its jobs.
- Hand a Workday job to `agentic_workday` later, when applying comes into scope.
