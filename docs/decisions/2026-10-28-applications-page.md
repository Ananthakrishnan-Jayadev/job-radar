# 2026-10-28: Applications page

**Asked for:** "a dashboard for the status of the application", read as the
user's job applications (where each stands), not the app's health.

**What it shows** (`jobradar/dashboard.py`, `GET /api/applications`,
`ApplicationsPage.tsx`):

- **Stages** saved → applied → interviewing → offer → rejected, as five
  counts in pipeline order, each linking to the Jobs list with that status
  (closed postings included). "Not interested" is a link in the summary line,
  not a stage.
- **Summary:** jobs ever applied to (an `applied_at` date, or a status from
  applied on), how many heard back (interview, offer or a no, now or at any
  point in the status history), and interviews.
- **Applications per week**, the last 12 weeks by `applied_at`, Monday-based.
  One series, so no legend; recessive grid; a tooltip on hover and on
  keyboard focus. Built from HTML bars rather than SVG so the labels stay
  readable at phone width. Colour: the "applied" status green, which passes
  3:1 against both theme surfaces.
- **Time to follow up:** applied or interviewing with no status change for
  14 days (`FOLLOW_UP_DAYS`), longest wait first.
- **In progress** and **Saved, not applied yet** tables, with the status
  select in place; a saved job whose posting closed is flagged.
- **Recent changes:** the last 15 status changes.

**Scope:** every job with a status other than "new", whatever its role,
location or whether the posting still exists, matching the rule that
tracking always shows.

**Not done:** response-time medians and per-company or per-level breakdowns
wait until there's enough data to make them mean something (3 tracked jobs
on the day it was built).
