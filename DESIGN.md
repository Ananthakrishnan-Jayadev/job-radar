---
name: Job Radar
description: A personal departures board for Canadian job postings, built for fast triage on a big monitor.
colors:
  board-navy: "#0c1b2c"
  board-panel: "#132539"
  board-raised: "#1a304a"
  strip-navy: "#081422"
  light-face: "#eef1f4"
  light-face-muted: "#9fb0c2"
  board-line: "#24405f"
  board-row-line: "#1b324c"
  board-select-wash: "#1b3350"
  wayfinding-yellow: "#ffc72c"
  lamp-yellow-print: "#f2b600"
  select-wash-print: "#fff3cc"
  concourse: "#e4e9ee"
  concourse-panel: "#f3f5f8"
  concourse-raised: "#fbfcfd"
  concourse-sunken: "#d7dfe7"
  slate-muted: "#4a5c70"
  concourse-line: "#c4cfda"
  concourse-row-line: "#d3dbe4"
  lake-blue: "#1d5b9e"
  lake-soft: "#cddcec"
  status-saved-print: "#8a5100"
  status-saved: "#f0a431"
  status-applied-print: "#186b3c"
  status-applied: "#2fb36c"
  status-closed-print: "#b8372a"
  status-closed: "#ff7a6a"
  status-not-interested-print: "#56636f"
  status-not-interested: "#8a9aac"
  status-interviewing-print: "#6a4bb0"
  status-interviewing: "#b59cff"
  status-offer-print: "#13703a"
  status-offer: "#5fd68f"
  status-rejected-print: "#9b4a40"
  status-rejected: "#e09a90"
typography:
  display:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.015em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  meta:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.68rem"
    fontWeight: 700
    letterSpacing: "0.08em"
  stamp:
    fontFamily: "Albert Sans Variable, Albert Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.09em"
rounded:
  tag: "3px"
  key: "4px"
  control: "6px"
  pill: "999px"
spacing:
  chip-gap: "0.3rem"
  column-gap: "0.6rem"
  board-inset: "1.25rem"
  screen-inset: "1.75rem"
  row-height: "3.35rem"
  top-strip: "3.25rem"
components:
  button:
    backgroundColor: "{colors.concourse-panel}"
    textColor: "{colors.board-navy}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-primary:
    backgroundColor: "{colors.board-navy}"
    textColor: "{colors.concourse}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-primary-dark:
    backgroundColor: "{colors.light-face}"
    textColor: "{colors.board-navy}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-quiet:
    textColor: "{colors.slate-muted}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  chip:
    textColor: "{colors.board-navy}"
    rounded: "{rounded.pill}"
    padding: "0.2rem 0.6rem"
  chip-on:
    backgroundColor: "{colors.board-navy}"
    textColor: "{colors.concourse}"
    rounded: "{rounded.pill}"
    padding: "0.2rem 0.6rem"
  filter-in-use:
    backgroundColor: "{colors.lake-soft}"
    textColor: "{colors.board-navy}"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.45rem 0.15rem 0.65rem"
  input:
    backgroundColor: "{colors.concourse-panel}"
    textColor: "{colors.board-navy}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.5rem"
  top-strip:
    backgroundColor: "{colors.strip-navy}"
    textColor: "{colors.light-face}"
    height: "{spacing.top-strip}"
  board-head:
    backgroundColor: "{colors.board-navy}"
    typography: "{typography.label}"
  board-head-dark:
    backgroundColor: "{colors.strip-navy}"
    textColor: "{colors.light-face-muted}"
    typography: "{typography.label}"
  board-row:
    typography: "{typography.title}"
    height: "{spacing.row-height}"
  board-row-selected:
    backgroundColor: "{colors.select-wash-print}"
  board-row-selected-dark:
    backgroundColor: "{colors.board-select-wash}"
  row-mark-selected:
    backgroundColor: "{colors.wayfinding-yellow}"
    textColor: "{colors.board-navy}"
  stamp-saved:
    textColor: "{colors.status-saved-print}"
    typography: "{typography.stamp}"
  stamp-applied:
    textColor: "{colors.status-applied-print}"
    typography: "{typography.stamp}"
  stamp-closed:
    textColor: "{colors.status-closed-print}"
    typography: "{typography.stamp}"
  stamp-not-interested:
    textColor: "{colors.status-not-interested-print}"
    typography: "{typography.stamp}"
  gate-screen:
    backgroundColor: "{colors.concourse-panel}"
    padding: "1.4rem 1.75rem 2rem"
  session-pill:
    backgroundColor: "{colors.concourse-raised}"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.65rem"
  toast:
    backgroundColor: "{colors.board-navy}"
    textColor: "{colors.concourse}"
    rounded: "{rounded.control}"
    padding: "0.6rem 0.8rem 0.6rem 1rem"
---

# Design System: Job Radar

## Overview

**Creative North Star: "The Departures Board"**

Every posting is a departure: one row, one time, one status, read at a glance. The Jobs page is a station departures board (the Pearson board is the reference), not a feed of cards and not a job board of stacked blurbs. Fixed columns are set once for the heads and every row and never reflow when the owner decides; a decision stamps into the status cell in place and the row stays where it is until the list refreshes.

Two themes share one board. **Dark** is the backlit board itself: navy ground and panels, light-face lettering. **Dim** (the default) is the same board printed on a light concourse panel: cool grey-blue grounds, navy ink, and the navy column-head strip and top strip kept from the backlit board. In both, a yellow-ruled navy top strip carries the wayfinding. Density is high and deliberate: the owner works on a big monitor in long sessions, so the board shows every column, the filter rail sits on the left and the selected posting (the gate screen) sits on the right, all three running edge to edge under the top strip.

Motion has one gesture: the stamp. Everything else is colour and border transitions under 0.2s, and all of it switches off under reduced motion.

**Key Characteristics:**
- Fixed-column board rows (tick, mark, posted, job + company, place, level, size, status) that never move on a decision.
- Navy top strip under a 3px wayfinding-yellow rule, in both themes.
- Yellow is rare and means "where you are" or "what's new"; status hues mean decisions.
- Capitals only in column heads and status stamps.
- One typeface, Albert Sans, with tabular figures everywhere.
- Flat tonal layers and 1px rules; shadow only for floating things.

## Colors

A navy-and-light-face board with one wayfinding yellow, a lake blue for links and heat in the printed theme, and a fixed set of status hues per theme.

### Primary
- **Board Navy** (board-navy): the ground of the dark theme, the ink of the dim theme, the column-head strip in dim, and the fill of the primary button, picked chips, the bulk bar and the toast in dim. It is the board's own material in both themes.
- **Strip Navy** (strip-navy): the top strip in both themes and the column-head strip in dark; the darkest navy, reserved for the board's header strips.
- **Light Face** (light-face): lettering on the backlit board: text in dark, top-strip text in both themes. In dark it also replaces lake blue as the link and focus colour, so the backlit board has no blue accent.

### Secondary
- **Wayfinding Yellow** (wayfinding-yellow): the 3px rule on the top strip (and the radar mark's dot and sweep inside it), the selected row's mark cell, the selected row's outline in dark, and the new-since-last-visit lamp in dark. Text on it is Board Navy.
- **Printed Lamp Yellow** (lamp-yellow-print): the new-since-last-visit lamp in dim, a deeper yellow with a thin navy ring so it reads on a light panel.

### Tertiary
- **Lake Blue** (lake-blue): links, focus rings, checkbox accents and the province heat map in dim; **Lake Soft** (lake-soft) is the fill of filters-in-use chips. The heat map steps through five mixes of lake into the panel (steps 1-3 take dark text, 4-5 light).
- **Status hues**, one per decision and one set per theme (the `-print` tokens are dim, the bare tokens dark): Saved amber, Applied green, Closed red, Not interested grey; Interviewing violet, Offer green and Rejected muted red serve the Applications pipeline. The same hue drives a job's stamp, its status dot and the wash of a decision button that's on.

### Neutral
- **Concourse** (concourse), **Concourse Panel** (concourse-panel), **Concourse Raised** (concourse-raised), **Concourse Sunken** (concourse-sunken): the dim theme's ground, panels (filter rail, gate screen, controls), raised pills and sunken tags.
- **Board Panel** (board-panel), **Board Raised** (board-raised): the dark theme's panels and raised pills.
- **Slate Muted** (slate-muted) / **Light Face Muted** (light-face-muted): secondary text (company line, hints, size text, column heads in dark).
- **Concourse Line** / **Board Line**: 1px panel and control borders. **Row lines** (concourse-row-line, board-row-line) are a step quieter than panel lines, so the board's rows read as one surface.
- **Select wash** (select-wash-print in dim, board-select-wash in dark): the fill of the row you're on.

### Named Rules
**The Wayfinding Yellow Rule.** Yellow appears in exactly three places: the top strip, the selected row's mark cell (and its outline in dark), and new-since-last-visit lamps. Never on buttons, chips, headings, charts or status.

**The Printed Board Rule.** In dim the selected row is outlined in navy (2px inset), not yellow: yellow cannot hold an outline on a light panel. Its mark cell still turns yellow, and the row takes the pale yellow wash.

**The Stamp Hue Rule.** Saved is amber, Applied green, Closed red, Not interested grey. "Not reviewed" has no stamp and no hue on the board; an empty status cell is the unreviewed state.

## Typography

**Display Font:** Albert Sans Variable (with Albert Sans, Segoe UI, system-ui, sans-serif)
**Body Font:** Albert Sans Variable (same stack)

**Character:** One geometric-grotesque family carries the whole board, the way a station sign system uses one face: weight and size do the ranking, tabular figures keep dates and counts aligned in their columns.

### Hierarchy
- **Display** (800, 2.75rem, 0.95): the job count at the head of the board, the board's one big line; its "jobs" unit sits beside it at 1rem 600 in muted. Steps to 2.1rem under 900px.
- **Headline** (800, 1.75rem, 1.12, balanced wrap): the posting title on the gate screen. Page titles elsewhere use 800 at 1.6rem.
- **Title** (700, 0.95rem): the job title in a board row, one line, ellipsis. Decided jobs drop to 550 and a faded ink so jobs still to review stand out; closed jobs are struck through in the closed red.
- **Body** (400, 15px, 1.5, tabular figures): everything else. The posting description stops at 75ch.
- **Meta** (400, 0.82rem): the company line under a job title (company, salary in green, and place or level when the board is narrow). Row cells run at 0.86rem; the posted date is 650 with a 0.7rem secondary line.
- **Label** (700, 0.68rem, 0.08em tracking, capitals): column heads of the board and of tables.
- **Stamp** (800, 0.7rem, 0.09em tracking, capitals): status stamps in the status cell, coloured by status hue.

### Named Rules
**The Two Capitals Rule.** Capitals appear only in column heads and status stamps. Everything else, buttons and nav included, is sentence case. Province codes (ON, BC) are abbreviations, not a style.

**The Tabular Rule.** Figures are tabular across the whole app (set on the body), so dates, counts and sizes line up down a column.

## Layout

The Jobs page is three panels edge to edge under the sticky top strip (3.25rem): a filter rail (17.5rem, foldable away so the results take the full width), the board, and, in the split view, the gate screen at `minmax(26rem, min(38rem, 42%))`. Filter rail and gate screen are sticky and scroll on their own; the board head is sticky at the top strip's edge, and the bulk bar covers it while jobs are ticked. Other pages sit in a centred `main` up to 1880px wide with 1.5rem by 2rem padding; reading pages narrow to 52rem or 64rem.

The board's columns are declared once as a grid template and shared by the head and every row: tick 2.25rem, mark 1rem, posted 3.75rem, job `minmax(0, 1fr)`, place 9.5rem, level 4.5rem, size 6.5rem, status 8.25rem (plus a 6.25rem decision column when the board is alone). Rows are at least 3.35rem tall with a 0.6rem column gap; the board's head area is inset 1.25rem, the gate screen 1.75rem.

**The Fold-In Rule.** The board responds to its own width (a container query), not the window's, and narrow columns fold into the company line rather than squeeze. Under 860px the size text goes and only the size dot stays. Under 760px Place moves into the company line. Under 480px Level joins it too, the size mark and row decision buttons go, and stamps may wrap. Reason: the owner works on a big monitor where every column shows, but at 1440px with filters and the posting open, the job column would otherwise be about 70px wide.

Under 900px window width the whole page becomes one column: the top strip wraps and stops being sticky, the nav scrolls sideways, and the filter rail moves below the board.

## Elevation & Depth

Flat by default. Depth is tonal: ground, panel, raised and sunken steps of the same navy or concourse grey, separated by 1px lines. The board itself has no shadow; the row you're on is marked by wash, a 2px inset outline and the yellow mark cell, not by lifting.

### Shadow Vocabulary
- **Ambient** (`box-shadow: 0 1px 2px rgb(12 27 44 / 0.06), 0 4px 14px -6px rgb(12 27 44 / 0.14)` in dim; `0 1px 2px rgb(0 0 0 / 0.3), 0 6px 18px -8px rgb(0 0 0 / 0.55)` in dark): province tiles and the few card-like panels on other pages.
- **Floating** (`box-shadow: 0 8px 28px -10px rgb(0 0 0 / 0.45)`): the undo toast, the one element that floats over the board.

### Named Rules
**The Flat Board Rule.** Rows, heads and panels never cast shadows. State on the board is shown by fill, outline and stamp.

## Shapes

Gently squared controls (6px) for buttons, inputs, selects, tiles and the toast; 4px for keycaps and skeleton bars; 3px for tags; full pills for chips, filters in use and the session count. Board rows and panels are square-edged and run edge to edge, joined by 1px rules. Dots are round: the size dot scales with company size (an empty ring when unknown), the status dot sits before a status select, and the new lamp is 0.5rem.

## Components

### Buttons
Quiet, sentence-case controls that recede until needed.
- **Shape:** gently squared (6px), 1px line border, panel fill, 0.35rem by 0.8rem.
- **Primary:** lettering lit up: filled with ink, text in the ground colour, 700 weight (navy with concourse text in dim; light face with navy text in dark and in the top strip).
- **Quiet:** transparent with muted text; gains the line border and panel fill on hover.
- **Hover / Focus:** border darkens to muted; focus is a 2px lake (or light-face) outline at 2px offset. Colour transitions 0.18s ease.

### Decision buttons
The three decisions (Save S, Not interested X, Applied A), each with a line icon and, on the gate screen, its keycap. A decision that's on takes its status hue: a 22% wash of the hue, the full hue as border and icon colour, ink text. Pressing it again takes the job back to Not reviewed.

### Chips
- **Filter chips:** pill, control-line border at 3:1 against the panel, 0.85rem text, wrap inside the rail. On: filled with ink, ground-colour text.
- **Filters in use:** pill in lake soft with a small x that brightens on hover; each removes itself. Shown above the board so nothing filters silently.

### Inputs / Fields
- **Style:** 1px line border, panel fill, 6px radius, 0.35rem by 0.5rem. Placeholders in muted at full opacity. Checkboxes take the lake accent.
- **Focus:** the shared 2px outline.

### Navigation
The top strip: strip navy under a 3px wayfinding-yellow rule, both themes, with its own backlit-board palette so controls in it read as lit. Brand mark (radar with a yellow dot whose sweep turns only while a scan runs) and name at 800; nav links muted at 500, current page in light face at 650 with a 2px light underline that slides between links.

### Board row (signature)
The departure line. Head: navy strip, column labels in the label style. Row: tick box, mark cell, posted date, job title over the company line, place, level, size dot and text, status cell. Hover adds a 4% ink wash; ticked adds a 7% neutral wash; the row you're on takes the select wash, a 2px inset outline (navy in dim, yellow in dark) and a yellow mark cell with a navy chevron.

### Status stamp (signature)
A decision stamps into the status cell in its hue and the board's capitals: it enters from 1.4x scale and transparent to rest in 0.22s on `cubic-bezier(0.16, 1, 0.3, 1)`, and leaves in 0.1s. The row never moves. Closed adds a red CLOSED stamp that stays alongside any decision.

### Gate screen
The selected posting beside the board: panel fill, left rule, headline title, company link at 650, the decision bar sticky at its top with a line of keycap hints, then a three-across facts grid (label over value) and the description at 75ch. It enters with a 0.2s rise of 12px.

### Session pill and toast
The session count is a raised pill beside the job count. The undo toast is an ink-filled bar at the bottom centre with a link-style Undo and its keycap; errors turn it danger red.

## Do's and Don'ts

### Do:
- **Do** set every board column once in the shared grid template so heads and rows align and nothing reflows on a decision.
- **Do** fold Place (under 760px board width) and then Level (under 480px) into the company line instead of squeezing columns.
- **Do** outline the selected row in navy in dim and in yellow in dark; turn its mark cell yellow in both.
- **Do** colour a status the same everywhere it appears: stamp, dot and decision-button wash.
- **Do** keep the navy top strip and its yellow rule in both themes.
- **Do** use tabular figures and Albert Sans for every surface.
- **Do** keep motion to the stamp, the gate screen's entrance and short colour transitions, and honour reduced motion.

### Don't:
- **Don't** use yellow outside the top strip, the selected row's mark cell and outline, and new-since-last-visit lamps.
- **Don't** set capitals anywhere but column heads and status stamps.
- **Don't** give Not reviewed a stamp or a hue on the board.
- **Don't** turn the board into cards or stacked blurbs, or move a row when its status changes.
- **Don't** cast shadows from rows, heads or panels.
- **Don't** add hover lifts or scattered hover effects on the board.
