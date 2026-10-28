# Plans still to build

Work that's planned but not scheduled into a phase. Phase 5 (polish and
hardening) is in [`../TASKS.md`](../TASKS.md); these come after it, or
between phases when they're wanted sooner. Each one gets a decision record
in [`decisions/`](decisions/) when it's built.

## 1. Add a job by its link ✅ built 2026-10-28

Moved here from phase 4 and built the same day: "Add a job by link" on the
Applications page and `jobradar add-job`
([decision](decisions/2026-10-28-backups-health-and-manual-jobs.md)).

## 2. Connectors for iCIMS, Avature and Oracle Cloud

Several companies moved to the archive on 2026-10-27 use these
([`decisions/2026-10-27-company-cleanup.md`](decisions/2026-10-27-company-cleanup.md)).
Each needs a check that its public job list can be read without logging in
before it's worth building. Item 1 covers single postings on them in the
meantime.

## 3. Small follow-ups

- **Cardinal Health:** its Workday link was cut off when you sent it, so the
  company stayed in the archive. With the full link it can come back.
- **Applications page:** reply-time averages and breakdowns by company or
  level, once enough jobs are tracked for them to mean something.

## 4. Version 2 ideas

The candidates listed in phase 5, task 7 (scheduled scans, a daily digest,
Job Bank CSV, Jooble, an MCP server, fit scores against your résumé through
Ollama, a hand-off to `agentic_workday`) are planned there.
