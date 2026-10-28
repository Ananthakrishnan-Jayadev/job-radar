# Plans still to build

Work that's planned but not scheduled into a phase. Phase 5 (polish and
hardening) is in [`../TASKS.md`](../TASKS.md); these come after it, or
between phases when they're wanted sooner. Each one gets a decision record
in [`decisions/`](decisions/) when it's built.

## 1. Add a job by its link

*Was phase 4, task 5; moved here on 2026-10-28 when phase 4 closed.*

**Why:** many big employers (banks, telecoms, Oracle, Avature, Dayforce,
iCIMS and Taleo users) post on job systems the app can't read as a feed, so
their jobs never show up. A job found there, or anywhere else, can't be
tracked on the Applications page today.

**How it would work:**
- Paste the link to one posting (Jobs page or company page).
- If the link is on a system the app knows (any of its 16, or one of the
  above where a single posting page can be read), the title, company,
  location and description are filled in from the page, for you to check.
- Otherwise a short form: title, company (picked from the list or added),
  location, and optionally the description pasted in.
- The job is stored like any other, marked as added by hand, so scans never
  close it. Tracking (status, notes, applied date) works the same, and it
  counts on the Applications page.
- Same job pasted twice: the existing one opens instead.

**Tests:** recognizing each known link format; reading a recorded posting
page; the manual form; manual jobs untouched by scans; duplicates.

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
