# Job Radar: start here

> **Status (2026-10-28):** this folder is the research from before any code
> was written. The app now exists (latest addition: experience level and
> years-asked filters). For how it works today, read the
> [README](../README.md), [PROJECT.md](../PROJECT.md) (the spec) and
> [decisions/](decisions/). Where this research and a decision disagree, the
> decision wins.

This folder holds the **research and decisions so far** for a personal job-hunting
tool. **No application code has been written yet, on purpose.** The next step is
to write a proper plan, task list and phases, and only then build.

Everything here came out of one Claude Code session on **2026-10-26**. It started
as a review of an open-source LinkedIn MCP server
(`~/Desktop/ai_projects/linkedin_mcp/linkedin-mcp-server`) and ended in the
decision to build a separate tool that does not depend on LinkedIn.

## Read in this order

| File | What it covers |
|---|---|
| [01-requirements.md](01-requirements.md) | What the user wants, in their words, plus the agreed scope |
| [02-linkedin-mcp-evaluation.md](02-linkedin-mcp-evaluation.md) | The full review of the LinkedIn MCP repo: strengths, gaps, what can be reused |
| [03-data-sources.md](03-data-sources.md) | **The core research:** every job and company data source, tested endpoints, access rules |
| [04-canadian-sources.md](04-canadian-sources.md) | Canada- and Ontario-specific sources, and why US tools fall short |
| [05-seed-companies.md](05-seed-companies.md) | Employers with verified feeds and Canadian roles, plus slug-collision warnings |
| [06-architecture-draft.md](06-architecture-draft.md) | The architecture and design choices proposed so far (a draft, not final) |
| [07-related-projects.md](07-related-projects.md) | The user's other projects that this can reuse from or connect to |
| [08-open-questions.md](08-open-questions.md) | Decisions still to make before or while planning |
| [09-plans.md](09-plans.md) | Plans still to build: more connectors, small follow-ups, version 2 ideas |
| [research/](research/) | Real sample responses from each API, probe scripts, draft code |

## Decisions already made

1. **Personal tool**, used by one person. It is not a product and not multi-user.
2. **Job hunting, not applying**, at least for now. The tool finds companies with
   matching postings, and the user marks jobs or companies as applied or not to
   track them. Auto-apply is out of scope for now. The user's separate
   `agentic_workday` project may be connected later.
3. **No LinkedIn automation in the core.** Using a personal LinkedIn session goes
   against LinkedIn's User Agreement and risks the account. The tool is built on
   public company job feeds and official or open APIs. At most, LinkedIn may be
   an optional, manual enrichment step later (see 02).
4. **Focus on Canada and Ontario.** Target roles include AI engineer and data
   analyst ("etc.", so the role list is configurable).
5. **This folder** (`~/Desktop/ai_projects/job-radar/`) is the project home.
   Planning documents (plan, tasks, phases) come next, before any code.

## Current state of the folder

- `.git/`: an empty repository (initialized, no commits).
- `.venv/`: a Python 3.14 virtual environment with `fastapi 0.162.0`,
  `httpx 0.28.1`, `uvicorn[standard]` and `pytest` installed. `uv` is **not**
  installed on this machine; `pip` + `venv` were used. Delete or rebuild the
  venv freely.
- `docs/research/draft-code/`: three files written before the user paused the
  build (`pyproject.toml`, `config.toml` with role regexes, `models.py` with
  `Job`/`Location` and Ontario-scope logic). Use them as reference, not as the
  starting point.

## The next step

The plan is written: [`../PROJECT.md`](../PROJECT.md) (specification) and
[`../TASKS.md`](../TASKS.md) (five phases). The answers to the open questions
are in [`decisions/2026-10-26-v1-scope-and-process.md`](decisions/2026-10-26-v1-scope-and-process.md).
Next: build phase 1.
