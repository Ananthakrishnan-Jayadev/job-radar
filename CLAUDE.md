# Job Radar: rules for Claude

Read `PROJECT.md` (the spec) and the ground rules at the top of `TASKS.md`
before working. The short version:

- **Install and build nothing.** No `pip install`, `npm install` or
  `npm run build`: the human runs them after each phase. Add dependencies to
  `pyproject.toml` / `frontend/package.json` and list the commands in the
  phase's manual checks. Packages only ever go into `.venv` (Python) or
  `frontend/node_modules` (JS); never `sudo`, `--user`, `npm -g`, `apt`,
  `pipx` or `curl | sh`.
- Use `.venv/bin/python` for anything Python.
- Run tests with `.venv/bin/pytest`. Tests never touch the network.
- No live scans against real sites without asking.
- UI: React + TypeScript in `frontend/`, built into `jobradar/web/static/`,
  served by FastAPI; `jobradar serve` is the only command to run it.
- One phase of `TASKS.md` at a time; end each with manual test instructions.
- Local git only, conventional commits.
