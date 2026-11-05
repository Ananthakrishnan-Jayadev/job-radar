# Jobs page: built for triage (2026-11-05)

**Asked for:** fix everything an Impeccable critique of the Jobs page found
(25/40; `.impeccable/critique/`), clutter and space first, with a split view
for triage; "choose what's best" for the split view.

**Why:** PRODUCT.md puts triage speed first (a big monitor, long sessions,
many quality applications), and the page was built for browsing: a 7-column
table, a 7-option status menu on every row, no keys, and a job page with the
decision far from the text.

**Decided:**

- **List, not table.** Two lines per job: title and date; company, size,
  place ("Toronto, ON +3", the full list on hover), level, salary when given.
  Status shows only once you've decided ("Not reviewed" shows nothing).
- **Split view** from 1440px wide (1100px with the filters hidden): the
  selected posting beside the list, sticky, with Save / Not interested /
  Applied and their keys at the top. A plain click on a title selects it;
  a new-tab click still opens its page. Narrower screens keep one column,
  with the three decisions on the row under the pointer or keyboard.
- **Decisions:** one press, the next job is selected; the row stays in place
  with its new status (rows vanishing after a change broke "never lose
  track"); an undo message for 8 seconds (`U`). Ticked jobs can be saved or
  dismissed together, also undoable.
- **Keys:** J/K, S/X/A, U, O, /, Esc. Ignored while typing in a box.
- **"New"** was on every row three times (status, tag, amber edge). Now: a
  small amber dot for new since your last visit; the status `new` reads
  "Not reviewed". The amber edge was a side stripe the design detector
  flags.
- **Start search:** in Saved searches, one search can open the Jobs page
  (kept in this browser). Chosen over a fixed default: the owner's radar
  changes as the search does.
- **Filters:** the address is tidied on load (a filter named twice is
  merged, unknown values dropped, `on` → `ON`): before, the chip showed one
  value while the server used another. The empty page counts what taking off
  each filter would bring back (one request per filter in use).
- **Smaller fixes:** selected province tiles look like selected chips (one
  "selected" look); chip and empty-tile borders at 3:1; placeholder text at
  4.5:1; province tiles read their full name to screen readers; the status
  menu ignores arrow keys while closed (Firefox changed and saved the status
  on them); no bounce on the status dot; a "Skip to the jobs list" link; the
  job page keeps tracking beside a 75-character description, in view; the
  sort says "Newest posted" when there are no words to match.

**Not done:** grouping one job listed once per city into one row. Each city
is its own posting, with its own status, on the company's board; grouping
needs a decision on what a status on the group means. Next/previous on the
full job page (the split view covers it).
