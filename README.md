# Job Radar

A personal job-hunting tool. It finds Canadian roles in public company job
feeds and job-search APIs, shows which companies are hiring and how big they
are, and lets you track what you've applied to.

**Status:** phase 1 of 5 done (foundation: database, location parser, company
list, command line). Next: phase 2, collecting jobs. See [TASKS.md](TASKS.md).

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
```

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
  cli.py           the `jobradar` command
seeds/             starting company list
tests/             pytest tests and recorded API responses
docs/              research and decisions
data/              the database (git-ignored)
```
