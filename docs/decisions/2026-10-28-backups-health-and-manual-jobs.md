# 2026-10-28: Backups, board health, open-roles history, adding a job by link

Phase 5 tasks 2–4, and the old phase 4 task 5, built together.

## Backups (`jobradar/backup.py`)

- **Why first:** statuses, notes and applied dates exist only in the
  database; a scan can rebuild everything else.
- **How:** SQLite's online backup API (`conn.backup`), so it's safe while a
  scan or the web app runs, then `PRAGMA integrity_check` on the copy; a
  failed check deletes it and says so.
- **Where:** next to the database, `jobradar-backup-YYYYMMDD-HHMMSS[-note].db`,
  the same naming as the copies made before bulk changes, so those count too.
- **Reminder:** the Scans page shows the newest backup and asks for a new
  one when it's 7 days old (`REMIND_AFTER_DAYS`) or there's none. No
  automatic backups: they'd need scheduling, which comes with scheduled scans.
- No pruning: the user deletes old copies.

## Board health

- A board is **failing** when its last 3 scans or more failed
  (`queries.FAILING_AFTER`), counted from `scan_results` since its last
  success. Switched-off boards aren't listed.
- Shown on the Scans page (company, board, streak, last success, last error,
  "Switch off"), on the company page next to the error, and by
  `jobradar failing-boards`. Fixing means adding the new board on the
  company page; nothing is switched off automatically.

## Open roles over time

- From `scan_results.jobs_canada`, no new data: per day, each board's last
  successful scan; a board that failed that day keeps its previous number,
  so a failed scan doesn't look like a hiring drop. Last 30 days with scans.
- Shown as a column chart on the company page. `BarChart.tsx` is shared with
  the Applications page's weekly chart: one series, no legend, recessive
  grid, a tooltip on hover and keyboard focus, labels thinned to about six.
  Company history uses the lake blue; applications keep the "applied" green.
  Both pass 3:1 against both theme surfaces.

## Adding a job by its link (`jobradar/manual.py`)

- **Reading the page:** most job sites embed a schema.org `JobPosting`
  (JSON-LD) for Google's job search, whatever system they run on (Workday,
  iCIMS, Taleo, Oracle, SmartRecruiters...), so one reader covers them all:
  title, company, city, region, country, remote, description, date posted,
  type, salary. A city alone resolves its province from the city list.
  Without it, the page title is used and the user fills in the rest. An
  unreadable page still gives an empty form.
- **The company** is matched by the link's job board if the app knows it,
  else by name; otherwise it's added.
- **Storage:** each company gets a `manual` board (switched off, no
  connector), so scans never read or close these jobs. Companies whose only
  board is `manual` still count as having no board for "find job boards".
- **Canada only:** saving needs a province or "remote in Canada"; the form
  warns when the page says the job is elsewhere.
- **Duplicates:** links are compared without tracking parameters
  (`utm_*`, `gh_src`...), fragment or trailing slash; the same link opens
  the stored job.
- The level and years are worked out from the description like any job.
