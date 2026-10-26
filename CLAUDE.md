# Job Radar: rules for Claude

Read `PROJECT.md` (the spec) and the ground rules at the top of `TASKS.md`
before working. The short version:

- **Never install anything outside `.venv`.** Use `.venv/bin/pip` /
  `.venv/bin/python` only. No `sudo`, `pip install --user`, system pip,
  `--break-system-packages`, `apt`, `snap`, `pipx`, `npm -g`, or
  `curl | sh`. If something outside the venv is needed, stop and ask.
- Run tests with `.venv/bin/pytest`. Tests never touch the network.
- No live scans against real sites, and no installs, without asking.
- One phase of `TASKS.md` at a time; end each with manual test instructions.
- Local git only, conventional commits.
