# Job Radar

A personal job-hunting tool for Canada. It reads the public job feeds of the
companies you care about (16 job systems, from Greenhouse to Workday), keeps
only jobs located in Canada and in the roles you want, and lets you search
them, filter by province, company size, experience level and years of
experience asked, and track what you've saved and applied to on an
Applications dashboard. It runs on your own computer: no LinkedIn
automation, no accounts.

- [PROJECT.md](PROJECT.md): the specification
- [docs/decisions/](docs/decisions/): why it works the way it does, dated
- [docs/00-START-HERE.md](docs/00-START-HERE.md): the research behind it

## Setup

Everything installs into the project's own folders, never system-wide:
Python packages into `.venv`, UI packages into `frontend/node_modules`.

```bash
cd ~/Desktop/ai_projects/job-radar
python3 -m venv .venv            # skip if .venv already exists
.venv/bin/pip install -e ".[dev]"
cp config.local.example.toml config.local.toml   # then add your email

# The web UI (needs Node 20+, for Tailwind)
cd frontend && npm install && npm run build && cd ..

.venv/bin/jobradar init-db       # create data/jobradar.db
.venv/bin/jobradar seed          # load the starting company list

# Only for "Apply" (filling in Greenhouse applications): the browser it drives,
# kept inside the venv, and your details (git-ignored)
PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install firefox
cp profile.example.toml profile.local.toml       # then fill it in
```

## Run the app

```bash
.venv/bin/jobradar serve        # then open http://127.0.0.1:8000
```

One command, one terminal: the Python server serves both the data and the
built UI. The UI has two themes, dim (low-glare light, the default) and dark;
the moon/sun button in the top bar switches them and is remembered. It's
built with React, Tailwind CSS, Motion (animations; turned off if your system
asks for reduced motion), Lucide icons and NumberFlow (animated counts). After changing anything in `frontend/`, run `npm run build` again,
or use `.venv/bin/jobradar serve --dev`, which rebuilds the UI on every save
(reload the page to see it).

### The pages

- **Jobs:** shows only the roles you want (software, data, AI; see "Which
  roles" below), with a "Show all roles" switch and role chips. Search (words,
  `"exact phrases"`, `OR`, `analy*`), a heat map of the ten provinces to
  filter by (live counts; territories are left out but count in "all of
  Canada") plus "Remote anywhere in Canada", and filters for experience level,
  company size, your status, workplace, date posted (from the last 24 hours to "more than a month ago"), job system and salary. Change a job's status right in the list; new jobs
  since your last visit have an amber edge. Save a search, export a CSV.
- **Applications:** where your tracked jobs stand. Counts for saved,
  applied, interviewing, offer and rejected (each opens the Jobs list with
  that status), how many applications heard back, applications per week for
  the last 12 weeks, the ones with no news for 14 days or more (time to follow
  up), tables of applications in progress and saved jobs not applied to yet
  (flagged when the posting has closed), and recent status changes.
  **Add a job by link** for a posting the app can't scan (Taleo, iCIMS,
  Oracle, a job site, LinkedIn): the details are read from the page (the
  schema.org job data most job sites embed for Google, or the page title)
  for you to check and complete, then the job is tracked like any other and
  never closed by a scan. The same link twice opens the stored job.
- **Job page:** description, Canadian locations, notes, applied date, status
  history, and links to the posting, the careers page and a LinkedIn search.
- **Companies:** roles matching yours, open roles in Canada and worldwide,
  size, job boards, your status. Buttons to fill in company sizes and to find job boards for
  companies that have none. Add a company (paste its careers link and let the
  app find its job board).
- **Company page:** boards (switch on or off, confirm a board matched by name,
  add one by pasting its link), size (type your own, or accept a Wikidata
  suggestion), notes, "scan this company now", and open roles in Canada over
  time (each day's last scan; a failed scan keeps the previous number). A
  board that failed 3 scans in a row says so.
- **Candidates:** companies listed on stillhiring.today; add the ones worth
  scanning.
- **Saved searches:** your saved views; mark the ones whose keywords big
  Workday sites (TD, RBC, BMO, CIBC) should be searched for.
- **Scans:** "Scan now", progress, and every past scan with per-board results.
  Boards that failed their last 3 scans or more are listed, with a button to
  switch each off (or fix it on its company page). Backups: when the newest
  is, a reminder after a week, and "Back up now".

## Applying (Greenhouse)

On a Greenhouse job's page, **Apply** fills in the company's real
application form for you to check and submit:

1. Pick a saved résumé, or upload one (kept in `data/resumes/`).
2. "Open pre-filled application": a browser window opens the form, filled in
   from `profile.local.toml`: name, email, phone (and its country), résumé,
   location, current company and title, LinkedIn and other links, work
   authorization, sponsorship, "how did you hear about
   us", notice and salary when you've set them, and your own `[answers]` to
   questions that come up often.
3. The panel lists what's left for you (questions about this job, anything
   the form didn't take) and what was a guess worth checking.
4. **You** read the form, answer the rest and press Submit (and solve a
   CAPTCHA if there is one). It never submits by itself.
5. When the form says thank you, the job is marked Applied, with a note of
   the résumé used. Closing the window first changes nothing.

Questions about gender, race, disability or veteran status are never
answered. Your profile stays on your computer (git-ignored); the job's
questions come from Greenhouse's public API, and nothing about you is sent
anywhere but the form you submit. `jobradar apply <job number> --resume
cv.pdf` does the same from the command line.

## Which roles

`roles.toml` decides which job titles count: software development, data
engineering & analysis, and AI development & implementation are on; an
"adjacent" group (business/systems analysts, IT support, product owners, data
governance...) is off. It was built from the real titles in the database
(see `docs/decisions/2026-10-26-role-keywords.md`), and its header explains
the rules. Every Canadian job is still stored; the rest are only hidden, and
jobs you're tracking always show. Edit the file and the change applies on the
next page load, no rescan. `jobradar search` and `export` take `--all-roles`.

## Experience level

Each wanted job gets a level: intern / co-op, entry, mid, senior or lead+.
Rules work it out, with no requests and the same answer every time:

1. **A level word in the title wins:** Intern, Co-op, Student → intern;
   Staff, Principal, Lead, Manager, Director, Head of, VP → lead+; Senior,
   Sr → senior; Intermediate → mid; Junior, Jr, New Grad, Associate → entry;
   "Engineer II" style grades (I entry, II mid, III/IV senior).
2. **Otherwise the years the description asks for:** "5+ years of
   experience", "5+ years building…", "at least 3 years in…", "2+ années
   d'expérience". When it names several, the largest counts ("10+ years in
   software, with 3+ years in Go" is 10); a range counts from its start
   ("7-10 years" is 7). 0–1 entry, 2–4 mid, 5–7 senior, 8+ lead+. Numbers over
   15, and ones after "for", "over", "since"... ("trusted for 10+ years") are
   the company's, not the job's.

A second filter, **years of experience asked**, picks under 3 (0–2), 3–5, or
more than 5 (6+), or "not stated". It only uses numbers the posting states.

Jobs neither rule places show as "Unknown" (about 1 in 12). A local
[Ollama](https://ollama.com) model can read the postings the rules left
without a level **or** without years, only when you say so: "Ask ..." under
the Experience filter, or `jobradar levels --ai`. It fills in only what's
missing (a level from the title stays), must always pick a level, and gives
years only when the posting states a number. Each job is read once; a
changed description is read again. Each job is asked about once; the answer is saved as
it comes, so stopping keeps what it got. The model is set in `config.toml`
(`[ollama] model`, default `gemma4:31b-cloud`); cloud models need
`ollama signin` once. Hover over a level in the list, or open the job, to see
the years asked and where the level came from.

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
.venv/bin/jobradar levels       # counts by level, and how many lack a level or years
.venv/bin/jobradar levels --ai  # ask Ollama to read those postings (once each)
.venv/bin/jobradar levels --ai --model nemotron-3-nano:30b-cloud --limit 50 --dry-run
```

Adding jobs by hand, backups and board health:

```bash
.venv/bin/jobradar add-job https://example.com/jobs/123 --status applied
.venv/bin/jobradar add-job <link> --title "Data Analyst" --company Acme --province ON
.venv/bin/jobradar backup --note before-cleanup   # dated, checked copy of the database
.venv/bin/jobradar failing-boards                 # boards that failed 3+ scans in a row
```

`add-job` reads the page like the web form; give `--title`, `--company` and
`--province` (or `--remote`) when the page doesn't say.

`levels --dry-run` prints the model's answers without saving them, to compare
two models on the same jobs before picking one. On 20 jobs, Gemma placed 11
and Nemotron 9 (they agreed on the rest), so Gemma is the default.

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
open roles. A source never overwrites a better one. "Fill in company sizes"
skips companies whose size came from a better source (your list, your own
entry), estimates the rest first, then asks Wikidata, saving every 20
companies, so a stopped run keeps what it found.

Options for any command: `--db PATH` uses another database file,
`--root PATH` reads `config.toml` from another folder.

## Your data

Everything lives in `data/jobradar.db` (git-ignored). The database upgrades
itself when a new version needs it. Your statuses, notes and applied dates
exist only there, so keep backups: `jobradar backup` or "Back up now" on the
Scans page writes `data/jobradar-backup-<date>.db` (an integrity-checked
copy, safe while the app runs), and the Scans page reminds you when the
newest is a week old. Delete old ones whenever you like.

Companies without a readable job board were moved out on 2026-10-27, to keep
the list to the ~215 that can be scanned. They're kept, with their boards,
jobs and research notes, in `data/removed-companies-*.db` (same format as the
main database) and `data/removed-companies-*.csv`. Re-importing `joblst.xlsx`
would bring some back.

To restore one, stop the server and copy it over the database:

```bash
cp data/jobradar-backup-20261028-120000.db data/jobradar.db
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
  snapshots.py       replaces Adzuna snapshot copies with the company's own board
  queries.py         job search with every filter, company lists, scan history
  tracking.py        statuses, notes, sizes, saved searches, "new since last visit"
  manual.py          adding a job by its link: reading the page, saving it
  apply/             filling in Greenhouse applications (plan answers, drive the browser)
  profile.py         your details for applications, from profile.local.toml
  resumes.py         résumés kept in data/resumes/
  backup.py          dated, checked copies of the database; the reminder
  dashboard.py       the Applications page: stages, weekly counts, follow-ups
  enrich.py          company sizes: precedence, Wikidata, estimates
  detect.py          finds a company's job board (link, careers page, name)
  boards.py          turns a pasted board link into a board name
  candidates.py      candidate companies from outside lists
  sources/           those lists (stillhiring.py)
  importer.py        imports your own .xlsx / .csv company lists
  roles.py           which titles are wanted, from roles.toml
  levels.py          experience level and years asked: rules, then Ollama on request
  export.py          CSV export
  cli.py             the `jobradar` command
  web/app.py         JSON API under /api, serves the built UI
  web/scanner.py     "Scan now" in a background thread
  web/tasks.py       other long jobs (sizes, finding boards, asking Ollama) in the background
  web/static/        the built UI (generated by npm run build; git-ignored)
frontend/            the React + TypeScript UI (Vite, Tailwind, Motion)
  src/styles.css     the two themes (colours as CSS variables) and all styles
  src/theme.tsx      the dim/dark switch
roles.toml           which roles you want (edit freely)
seeds/               starting company list
tests/               pytest tests and recorded API responses
docs/                research and decisions
data/                the database and backups (git-ignored)
```
