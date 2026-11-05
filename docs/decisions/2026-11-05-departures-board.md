# The Jobs page as a departures board (2026-11-05)

The colour pass left the app looking the same as before, so the Jobs page got
a new look rather than more polish. Four directions were sketched (a
departures board, a topographic survey sheet, a transit diagram, a standard
job board); the departures board was picked.

## What it means

- **Every posting is a departure:** one row, one date, one status, read at a
  glance. The list is a board with fixed columns (posted, job and company,
  place, level, company-size dot, status) set once for the heads and every
  row, so nothing moves when you decide.
- **Statuses stamp in place:** Save, Not interested and Applied stamp their
  name, in capitals and in the status's colour, into the status column with
  one short animation. Closed jobs read CLOSED in red and keep a struck title.
- **Capitals only** in column heads and stamps. One face, Albert Sans, with
  tabular figures; the job count is the one large line.
- **Panels edge to edge** under the top bar: filters on the left, the board,
  the selected job on the right (title, decisions, facts three across, then
  the description).
- **Narrow windows fold rather than squeeze:** under about 760px of board
  width, place moves under the company name; under 480px, level joins it and
  the size dot goes. On a phone the count and list come before the filters.

## Colours

First built in navy and wayfinding yellow; the owner didn't like yellow or
blue, so it became **forest and mint** the same day: evergreen panels and
header strips, light mint only for the top rule, the row you're on and new-job
dots. Links take the ink colour, because a green link looked like the green
Applied status. Status colours stay: Saved amber, Applied green, Closed red,
Not interested grey.

The font is a new package (`@fontsource-variable/albert-sans`): run
`npm install` in `frontend/` once before building.

## Checks

Reviewed against the direction (five fixes: one-line stamps, a labelled size
column, no stray accent colour, the board's dark head strip in the light
theme, count and list first on phones). The design checker reports nothing on
the Jobs page. `DESIGN.md` records the system.
