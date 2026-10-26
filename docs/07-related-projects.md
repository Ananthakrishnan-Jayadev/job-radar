# The user's related projects (under `~/Desktop/ai_projects/`)

## `linkedin_mcp/linkedin-mcp-server`

The LinkedIn MCP server reviewed in `02-linkedin-mcp-evaluation.md`. An optional,
manual enrichment source at most. Reusable ideas are listed in 02 under "What can
be reused".

## `agentic_workday`: Workday auto-apply (the user's own project)

- "A personal-use tool that fills out and submits Workday job applications on
  your behalf." A Playwright harness plus a local LLM (Gemma 4 through Ollama)
  for judgment calls, with two human checkpoints (email confirmation at signup,
  and a final review before submitting).
- Stack: Python 3.11+, Playwright (async), Ollama, Pydantic, **FastAPI + Uvicorn**,
  **YAML** for the profile and config, **plain HTML, JavaScript and CSS** front
  end.
- Has `project.md` (specification), `task.md` (phased build plan),
  `profile.example.yaml`, `config.yaml`, `app/` (`harness.py`, `orchestrator.py`,
  `resolve.py`, `field_map.py`, `tenants.py`, `job_state.py`, `receipts.py`,
  `llm.py`, ...).
- **Its non-goals include "auto-discovery of jobs / job matching. The user
  supplies the URL."** That is exactly the gap job-radar fills. Later, job-radar
  can pass Workday job URLs to it.
- `app/tenants.py` records which Workday **tenants** (hosts) the user already
  has accounts on, stored as JSON (`host → {slug, first_seen, last_used}`).
  job-radar could read this to flag "you already have an account on this
  company's Workday".
- **Its process convention:** "the implementing agent writes code and creates
  files only. It must not run, test, install, or execute anything", and "do one
  phase at a time; at the end of each phase, stop, the human installs, runs and
  verifies". **Ask the user whether job-radar should follow the same rule.**
  This session did run network probes and created a venv.
- The `project.md` + `task.md` split, with phases and ground rules, is a good
  template for job-radar's plan.

## `hireflow` (ShyftHatch): an AI applicant tracking system (recruiter side)

- FastAPI + PostgreSQL (SQLAlchemy async, Alembic) + a plain JavaScript single
  page app. JWT auth, pipeline board, analytics.
- It's the **employer** side, but its pipeline and kanban ideas (stages,
  drag-and-drop between them) carry over to the job-seeker side: a kanban of
  saved → applied → interviewing → offer.
- Probably more stack than a personal tool needs (Postgres, Redis, auth). Borrow
  UI patterns, not infrastructure.

## `workday_extension`: Workday autofill browser extension

- A Chrome/Edge Manifest V3 extension that fills Workday forms on
  `myworkdayjobs.com` from a local `data.json`.
- Not needed for job hunting. A possible later companion for applying.

## Other folders seen (not inspected)

`Engram`, `Life-OS`, `adaptive_brain`, `agent_file`, `board`, `fifa_fantasy`,
`local_ai`, `marketplace-ai-monitor`, `portfolio`, `translator`, `tv`,
`vending_machine`, `worldcup-2026-simulator`, `worldmonitor`.
`marketplace-ai-monitor` and `worldmonitor` may contain monitoring or scheduling
patterns worth a look; not checked.
