# 2026-10-26: Adzuna as a one-time snapshot, not a source

Adzuna's free tier turned out to be **25 test calls in total** ("Pending
Activation"); real use is £8/month for 5,000 calls a month and 500 a day.
Third-party guides quoting 250/day free were out of date. The user won't
pay, so phase 4's Adzuna connector and its deduplication are dropped.

The 25 test calls were spent once (23 used, 2 kept) on Canadian searches,
newest first, last 30 days, 50 results per call: data analyst, data
scientist, machine learning, AI engineer, data engineer, business
intelligence, analytics engineer. A mistake in the one-off script gave 17
of the 23 calls to "data engineer" (it always picked the term with the most
results left); the other terms got one page each.

Result: 962 unique jobs from 602 employers. Stored: **484 jobs from 327
employers new to the list**, after dropping titles outside data/AI/analytics
(424, Adzuna matches descriptions too), jobs at companies already scanned
from their own board (47, including legal-name variants such as "Bank of
Montreal" for BMO), and job sites posing as employers (7: Jobgether,
Turing...). None of the user's ~70 companies without a readable board
appeared, so Adzuna didn't fill that gap.

How they're kept:
- Each new employer is a company with a board of system `adzuna`. It has no
  connector, so scans never touch it and the jobs are **never refreshed or
  closed**; the company's notes say so, and the system shows as "Adzuna
  (one-time snapshot)".
- Descriptions are Adzuna's snippets; links go through Adzuna's redirect.
  Predicted salaries are dropped, published ones kept.
- `find-boards` ignores `adzuna` boards, so it can look for these companies'
  real job boards; once found, they are scanned like any other company.
- The raw responses (without the key) are kept outside the repo, in the
  session's scratch folder, not as test fixtures.

## Update, same day: the company's own board replaces the copies

Instead of fetching Adzuna's own job pages for full descriptions (that's
Adzuna's website, and its links record ad clicks), a scan now settles the
copies itself (`jobradar/snapshots.py`). When a company's **confirmed** board
is read completely and without error:

- a copy whose title matches a board job (the same title, or the same title
  plus Adzuna's extras: a Canadian place, "New", "Remote", the salary line)
  hands over its status, notes, applied date and status history, and is
  deleted;
- a copy with no match is closed, since the board no longer lists that job in
  Canada;
- a snapshot board left with no jobs is removed.

Matching is strict on purpose ("Senior Software Engineer" never matches
"Senior Software Engineer, Data Infrastructure"): a miss only closes the copy,
and the board's own job is there anyway. Guessed (unconfirmed) boards don't
retire anything until you confirm them. Companies without a board of their own
keep their snippets.
