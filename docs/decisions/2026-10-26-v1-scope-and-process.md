# 2026-10-26: Version 1 scope and process

Answers to `docs/08-open-questions.md`, given by the user while planning.

| # | Question | Decision |
|---|---|---|
| 1 | Target roles | **No fixed role list.** Jobs are searched by free-text keywords. Saved searches hold the user's usual queries and also drive sources that search on their own side (Workday over a size limit, Adzuna). |
| 2 | Locations | **All of Canada**, with a **province filter** (plus "Remote, Canada-wide"). |
| 3 | Work authorization | Not filtered. |
| 4 | Company size | A **usable filter** by size band (under 50, 50–199, 200–999, 1,000–4,999, 5,000+, Unknown). |
| 5 | Extra features in v1 | "New since last visit", filters, notes, salary column, CSV export, hide ignored companies. Later: momentum charts, digests, LLM fit scores. |
| 6 | Tracking | Both jobs and companies. Jobs: new → saved → applied → interviewing → offer / rejected, plus not_interested. Companies: target, watching, ignored. |
| 7 | Agent rules | The agent writes code **and pytest tests**, runs pytest, and writes **manual test instructions** for each phase. No installs or live scans without asking. |
| 8 | Plan format | `PROJECT.md` + `TASKS.md`, dated decision records in `docs/decisions/`. |
| 9 | Git | Commit regularly, conventional commits, **local only** for now. Branch renamed `master` → `main`. |
| — | Phases | **Five** phases (user asked for fewer than six). |
| — | Language | **Python** as the main language; UI is Jinja2 + htmx so almost no JavaScript. |
| 10 | Interface | **Web UI in v1**, plus a CLI. MCP server later. |
| 11 | Config format | TOML. |
| 12 | Package manager | `pip` + `venv`. |
| 13 | Scheduling | **On demand** in v1. |
| 14 | Aggregator keys | The user will sign up for what's needed (Adzuna before phase 4). Jooble later. |
| 15 | Company size data | Wikidata, then an estimate; manual entry always available and always wins. |
| 16 | Job Bank CSV | Later (check for employer names first). |
| 17 | Dayforce / iCIMS / Taleo gap | Covered by Adzuna plus "add job by URL". |
| 18 | LinkedIn | Plain search links only, no automation. |
| 19 | Notifications | None in v1. |
| 20 | LLM features | None in v1. |

Consequence of decision 1: feeds store **every Canadian job** they return
(not only jobs matching roles), so any keyword can be searched later.
