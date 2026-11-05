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

## Colour pass (same day)

Colour now carries state, within the existing palette (granite, lake,
spruce; amber only for "new"):

- **Province map in five steps** of lake instead of a smooth ramp. The
  middle of the ramp failed contrast with both dark and light text (2.9:1);
  steps 1–3 take dark text, 4–5 light, all at 4.5:1 or better in both themes.
- **Selected vs ticked:** selected is a lake wash with a 2px lake outline;
  ticked is a neutral wash plus the tick. Before, they differed by 6% of lake.
  Secondary text on the selected row is tinted from ink and lake (4.2:1 grey
  before).
- **Statuses in their own colour:** a decided row's badge is a soft wash of
  its status hue; an active Save / Not interested / Applied button takes the
  same hue as its border and icon, with ink text.
- **"New" dots** disappear when every job on the page is new; one line says
  so instead.
- **Dark theme:** the Scan button's coloured glow is a plain shadow.

The design checker reports nothing on the Jobs page in either theme.

## Second critique round (same day)

- **Room for the list:** the posting stops at reading width (about 47rem);
  the list takes the rest, so hiding the filters widens the list.
- **Progress:** "N decided this session" beside the job count (jobs moved
  from Not reviewed to a decision in this tab; undo and taking a job back
  count down). Decided rows step back with a lighter title.
- **Keyboard:** `T` or Space ticks the selected job; Shift-click ticks a
  range; `S`/`X`/`A` act on the ticked jobs when there are any (before, `A`
  hit the selected job instead); `J` past the last job opens the next page,
  `K` before the first the previous one. `S`/`X`/`A` also work on the full
  job page. Bulk has Applied too.
- **Honest dates:** a posting with no date shows "Found Nov 5" in the list,
  and "Posted: Not given" plus "Found" in the preview.
- Descriptions lose runs of blank lines; a failed load says what to do
  instead of "500 Internal Server Error".
