# Job Radar

A personal job-hunting tool for Canada. It reads the public job feeds of the
companies you care about, keeps only jobs located in Canada, and lets you
search them, filter by province and company size, and track what you've
saved and applied to. No LinkedIn automation, no accounts.

**Status:** phases 1–3 of 5 done; phase 4 part 1 done (company sizes,
stillhiring.today candidates, job-board detection, importing your own company
lists), plus five more job systems than planned. Next: phase 4 part 2 (Adzuna
job search, needs a free key). See [TASKS.md](TASKS.md).

- [PROJECT.md](PROJECT.md): the specification
- [TASKS.md](TASKS.md): the build plan in five phases
- [docs/00-START-HERE.md](docs/00-START-HERE.md): the research behind it
- [docs/decisions/](docs/decisions/): decisions, dated

## Setup

Everything installs into the project's own folders, never system-wide:
Python packages into `.venv`, UI packages into `frontend/node_modules`.

```bash
cd ~/Desktop/ai_projects/job-radar
python3 -m venv .venv            # skip if .venv already exists
.venv/bin/pip install -e ".[dev]"
cp config.local.example.toml config.local.toml   # then add your email

# The web UI (needs Node 18+)
cd frontend && npm install && npm run build && cd ..

.venv/bin/jobradar init-db       # create data/jobradar.db
.venv/bin/jobradar seed          # load the starting company list
```

## Run the app

```bash
.venv/bin/jobradar serve        # then open http://127.0.0.1:8000
```

One command, one terminal: the Python server serves both the data and the
built UI. After changing anything in `frontend/`, run `npm run build` again,
or use `.venv/bin/jobradar serve --dev`, which rebuilds the UI on every save
(reload the page to see it).

### The pages

- **Jobs:** shows only the roles you want (software, data, AI; see "Which
  roles" below), with a "Show all roles" switch and role chips. Search (words,
  `"exact phrases"`, `OR`, `analy*`), a tile map of
  Canada to filter by province (with live counts) plus "Remote anywhere in
  Canada", and filters for company size, your status, workplace, date posted,
  job system and salary. Change a job's status right in the list; new jobs
  since your last visit have an amber edge. Save a search, export a CSV.
- **Job page:** description, Canadian locations, notes, applied date, status
  history, and links to the posting, the careers page and a LinkedIn search.
- **Companies:** open roles in Canada and worldwide, size, job boards, your
  status. Buttons to fill in company sizes and to find job boards for
  companies that have none. Add a company (paste its careers link and let the
  app find its job board).
- **Company page:** boards (switch on or off, confirm a board matched by name,
  add one by pasting its link), size (type your own, or accept a Wikidata
  suggestion), notes, and "scan this company now".
- **Candidates:** companies listed on stillhiring.today; add the ones worth
  scanning.
- **Saved searches:** your saved views; mark the ones whose keywords big
  Workday sites (TD, RBC, BMO, CIBC) should be searched for.
- **Scans:** "Scan now", progress, and every past scan with per-board results.

## Which roles

`roles.toml` decides which job titles count: software development, data
engineering & analysis, and AI development & implementation are on; an
"adjacent" group (business/systems analysts, IT support, product owners, data
governance...) is off. It was built from the real titles in the database
(see `docs/decisions/2026-10-26-role-keywords.md`), and its header explains
the rules. Every Canadian job is still stored; the rest are only hidden, and
jobs you're tracking always show. Edit the file and the change applies on the
next page load, no rescan. `jobradar search` and `export` take `--all-roles`.

## Job systems it reads (16)

| System | Read from | Example companies |
|---|---|---|
| Greenhouse, Lever, Ashby, SmartRecruiters | Official public job APIs | Stripe, Wattpad, Cohere, Canva |
| Workable, Recruitee, Breezy, Rippling | Public job widgets and feeds | Borrowell, nesto, Personify |
| BambooHR | Careers list (undocumented) | Asigra, Block 64, NexJ Health |
| Workday | Careers site search (undocumented) | TD, RBC, BMO, CIBC, Sun Life, Manulife |
| SAP SuccessFactors | The site's job feed (`/sitemap.xml`) | Scotiabank |
| JazzHR | Its XML job feed | Xello, Apertera, Cognota |
| Pinpoint | Its JSON job feed | Crawford Technologies |
| Teamtailor | Its RSS job feed | commonsku |
| Humi | The careers page's HTML (no feed; the most fragile) | Ecopia.AI, Hypercare |
| HiBob | The careers app's JSON (undocumented) | Xanadu |

Only jobs with a location in Canada are kept (or, for Canadian companies,
postings that say nothing but "Remote"). Where a list has no job
descriptions, each wanted role's own page is read during the scan, up to 60
per board per scan (`[details]` in `config.toml`); the rest follow on the
next scan.

The jobs from the one-time Adzuna snapshot only have snippets. Once a
company's confirmed board has been read in full, its Adzuna copies are
replaced: matching jobs move your tracking over to the board's job, and the
rest are closed. Details and quirks of each source:
[docs/03-data-sources.md](docs/03-data-sources.md).

## Commands

Run these from the project folder (or activate the venv with
`. .venv/bin/activate` and drop the `.venv/bin/` prefix).

```bash
.venv/bin/jobradar init-db      # create or upgrade data/jobradar.db
.venv/bin/jobradar seed         # load seeds/companies.toml (safe to repeat)
.venv/bin/jobradar companies    # list companies and their job boards
.venv/bin/jobradar scan         # fetch jobs from every enabled board
.venv/bin/jobradar scan --company "Cohere"     # just one company
.venv/bin/jobradar search machine learning     # newest/most relevant matches
.venv/bin/jobradar search '"data analyst"' --province ON,REMOTE
.venv/bin/jobradar export --out ~/jobs.csv --province ON
.venv/bin/jobradar enrich       # fill company sizes (Wikidata, then estimates)
.venv/bin/jobradar candidates refresh   # read stillhiring.today
.venv/bin/jobradar candidates list      # companies waiting for your decision
.venv/bin/jobradar detect "Docebo" --url https://jobs.ashbyhq.com/docebo
.venv/bin/jobradar import-companies mylist.xlsx  # add companies from your own list
.venv/bin/jobradar find-boards  # find job boards for companies that have none
```

Search accepts words, `"exact phrases"`, `OR` and prefixes (`analy*`).
`--province` takes codes (ON, BC, QC...) and `REMOTE` for jobs open
anywhere in Canada; leave it out for all of Canada. Add `--include-closed`
to see jobs that have disappeared from their board.

A scan prints one line per board: how many of its jobs are in Canada, how
many are new or closed, and any errors. A failing board doesn't stop the
others. To fix a wrong board, open the company in the web app: switch the old
board off and add the right one by pasting its link.

**Importing your own company list** (`.xlsx` or `.csv`): a sheet with a
"Company" column, where the first real link in each row is taken as the careers
page (Google and LinkedIn search links are skipped); and/or lines like
"Acme (51-200)" under headings, which set the size and go into the notes.
Existing companies are never overwritten, only filled in. `find-boards` then
reads careers pages and tries each company's name on the common job systems;
boards found by name only are added as *unconfirmed*: check them on the
company page.

**Company sizes** come from, best first: your own entry, stillhiring.today,
your imported list ("51-200" counts as 125), Wikidata, then an estimate from
open roles. A source never overwrites a better one.

Options for any command: `--db PATH` uses another database file,
`--root PATH` reads `config.toml` from another folder.

## Your data

Everything lives in `data/jobradar.db` (git-ignored). The database upgrades
itself when a new version needs it. Bulk changes made for you (imports,
board research) were preceded by a copy in `data/jobradar-backup-*.db`;
delete old ones whenever you like. To make your own copy:

```bash
cp data/jobradar.db data/jobradar-$(date +%F).db   # with the server stopped
```

## Tests

```bash
.venv/bin/pytest
```

Tests never touch the network; they use recorded responses in
`tests/fixtures/` and write only to temporary folders.

## Layout

```
jobradar/            the package
  config.py          settings from config.toml + config.local.toml
  models.py          Location, RawJob, Board, size bands, statuses
  locations.py       location parser (Canada / province / remote)
  db.py              SQLite schema, migrations, connections
  seed.py            loads seeds/companies.toml
  http.py            shared HTTP client: per-host limits, pauses, retry
  connectors/        one module per job system (greenhouse.py, workday.py...)
  scan.py            runs connectors, stores Canadian jobs, closes vanished ones
  queries.py         job search with every filter, company lists, scan history
  tracking.py        statuses, notes, sizes, saved searches, "new since last visit"
  enrich.py          company sizes: precedence, Wikidata, estimates
  detect.py          finds a company's job board (link, careers page, name)
  boards.py          turns a pasted board link into a board name
  candidates.py      candidate companies from outside lists
  sources/           those lists (stillhiring.py)
  importer.py        imports your own .xlsx / .csv company lists
  roles.py           which titles are wanted, from roles.toml
  export.py          CSV export
  cli.py             the `jobradar` command
  web/app.py         JSON API under /api, serves the built UI
  web/scanner.py     "Scan now" in a background thread
  web/tasks.py       other long jobs (sizes, finding boards) in the background
  web/static/        the built UI (generated by npm run build; git-ignored)
frontend/            the React + TypeScript UI (Vite)
roles.toml           which roles you want (edit freely)
seeds/               starting company list
tests/               pytest tests and recorded API responses
docs/                research and decisions
data/                the database and backups (git-ignored)
```
