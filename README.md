# Job Radar

A personal job-hunting tool. It finds Canadian roles in public company job
feeds and job-search APIs, shows which companies are hiring and how big they
are, and lets you track what you've applied to.

**Status:** phases 1–2 of 5 done (database, location parser, company list,
connectors for 10 job systems, scanning, search and CSV export). Next:
phase 3, the web UI. See [TASKS.md](TASKS.md).

- [PROJECT.md](PROJECT.md): the specification
- [TASKS.md](TASKS.md): the build plan in five phases
- [docs/00-START-HERE.md](docs/00-START-HERE.md): the research behind it
- [docs/decisions/](docs/decisions/): decisions, dated

## Setup

Everything installs into the project's own `.venv`, never system-wide.

```bash
cd ~/Desktop/ai_projects/job-radar
python3 -m venv .venv            # skip if .venv already exists
.venv/bin/pip install -e ".[dev]"
cp config.local.example.toml config.local.toml   # then add your email
```

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
```

Search accepts words, `"exact phrases"`, `OR` and prefixes (`analy*`).
`--province` takes codes (ON, BC, QC...) and `REMOTE` for jobs open
anywhere in Canada; leave it out for all of Canada. Add `--include-closed`
to see jobs that have disappeared from their board.

A scan prints one line per board: how many of its jobs are in Canada, how
many are new or closed, and any errors. A failing board doesn't stop the
others. To fix a wrong slug (or Workday URL) until the web UI can edit boards:
in `seeds/companies.toml`, add `enabled = false` to the old board, add the
corrected board, and run `jobradar seed` again.

Options for any command: `--db PATH` uses another database file,
`--root PATH` reads `config.toml` from another folder.

## Tests

```bash
.venv/bin/pytest
```

Tests never touch the network; they use recorded responses in
`tests/fixtures/` and write only to temporary folders.

## Layout

```
jobradar/          the package
  config.py        settings from config.toml + config.local.toml
  models.py        Location, RawJob, Board, size bands, statuses
  locations.py     location parser (Canada / province / remote)
  db.py            SQLite schema, migrations, queries, full-text search
  seed.py          loads seeds/companies.toml
  http.py          shared HTTP client: per-host limits, pauses, retry
  connectors/      one module per job system (greenhouse.py, workday.py...)
  scan.py          runs connectors, stores Canadian jobs, closes vanished ones
  export.py        CSV export
  cli.py           the `jobradar` command
seeds/             starting company list
tests/             pytest tests and recorded API responses
docs/              research and decisions
data/              the database (git-ignored)
```
