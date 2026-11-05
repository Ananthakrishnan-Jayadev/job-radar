---
name: Job Radar
description: A personal departures board for Canadian job postings, built for fast triage on a big monitor.
colors:
  evergreen: "#0d211b"
  evergreen-ink: "#10241c"
  evergreen-panel: "#132c24"
  evergreen-raised: "#1a382e"
  evergreen-strip: "#091812"
  light-face: "#edf3ee"
  light-face-muted: "#a3b8ad"
  evergreen-line: "#24453a"
  evergreen-row-line: "#1b382e"
  evergreen-select-wash: "#1b3d31"
  head-face-print: "#b7cbbf"
  light-mint: "#a8e6a3"
  lamp-mint-print: "#7fd27a"
  mint-wash-print: "#e2f4de"
  sage: "#e5ebe6"
  sage-panel: "#f3f6f3"
  sage-raised: "#fafcfa"
  sage-sunken: "#d6e0d8"
  moss-muted: "#4a5f54"
  sage-line: "#c3d1c7"
  sage-row-line: "#d3ded6"
  forest-soft: "#d2e6d7"
  status-saved-print: "#8a5100"
  status-saved: "#f0a431"
  status-applied-print: "#186b3c"
  status-applied: "#3fbf73"
  status-closed-print: "#b8372a"
  status-closed: "#ff7a6a"
  status-not-interested-print: "#56665d"
  status-not-interested: "#8fa39a"
  status-interviewing-print: "#6a4bb0"
  status-interviewing: "#c4a6ff"
  status-offer-print: "#13703a"
  status-offer: "#7fe0a0"
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
    backgroundColor: "{colors.sage-panel}"
    textColor: "{colors.evergreen-ink}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-primary:
    backgroundColor: "{colors.evergreen-ink}"
    textColor: "{colors.sage}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-primary-dark:
    backgroundColor: "{colors.light-face}"
    textColor: "{colors.evergreen}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  button-quiet:
    textColor: "{colors.moss-muted}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.8rem"
  chip:
    textColor: "{colors.evergreen-ink}"
    rounded: "{rounded.pill}"
    padding: "0.2rem 0.6rem"
  chip-on:
    backgroundColor: "{colors.evergreen-ink}"
    textColor: "{colors.sage}"
    rounded: "{rounded.pill}"
    padding: "0.2rem 0.6rem"
  filter-in-use:
    backgroundColor: "{colors.forest-soft}"
    textColor: "{colors.evergreen-ink}"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.45rem 0.15rem 0.65rem"
  input:
    backgroundColor: "{colors.sage-panel}"
    textColor: "{colors.evergreen-ink}"
    rounded: "{rounded.control}"
    padding: "0.35rem 0.5rem"
  top-strip:
    backgroundColor: "{colors.evergreen-strip}"
    textColor: "{colors.light-face}"
    height: "{spacing.top-strip}"
  board-head:
    backgroundColor: "{colors.evergreen-ink}"
    textColor: "{colors.head-face-print}"
    typography: "{typography.label}"
  board-head-dark:
    backgroundColor: "{colors.evergreen-strip}"
    textColor: "{colors.light-face-muted}"
    typography: "{typography.label}"
  board-row:
    typography: "{typography.title}"
    height: "{spacing.row-height}"
  board-row-selected:
    backgroundColor: "{colors.mint-wash-print}"
  board-row-selected-dark:
    backgroundColor: "{colors.evergreen-select-wash}"
  row-mark-selected:
    backgroundColor: "{colors.light-mint}"
    textColor: "{colors.evergreen-ink}"
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
    backgroundColor: "{colors.sage-panel}"
    padding: "1.4rem 1.75rem 2rem"
  session-pill:
    backgroundColor: "{colors.sage-raised}"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.65rem"
  toast:
    backgroundColor: "{colors.evergreen-ink}"
    textColor: "{colors.sage}"
    rounded: "{rounded.control}"
    padding: "0.6rem 0.8rem 0.6rem 1rem"
---

# Design System: Job Radar

## Overview

**Creative North Star: "The Departures Board"**

Every posting is a departure: one row, one time, one status, read at a glance. The Jobs page is a station departures board in its form, not a feed of cards and not a job board of stacked blurbs. Fixed columns are set once for the heads and every row and never reflow when the owner decides; a decision stamps into the status cell in place and the row stays where it is until the list refreshes.

The board is set in forest and mint. **Dark** is the backlit board itself: evergreen ground and panels, light-face lettering. **Dim** (the default) is the same board printed on a pale sage panel: green-grey grounds, evergreen ink, and the evergreen column-head strip and top strip kept from the backlit board. In both, a mint-ruled evergreen top strip carries the wayfinding. Density is high and deliberate: the owner works on a big monitor in long sessions, so the board shows every column, the filter rail sits on the left and the selected posting (the gate screen) sits on the right, all three running edge to edge under the top strip.

Motion has one gesture: the stamp. Everything else is colour and border transitions under 0.2s, and all of it switches off under reduced motion.

**Key Characteristics:**
- Fixed-column board rows (tick, mark, posted, job + company, place, level, size, status) that never move on a decision.
- Evergreen top strip under a 3px light-mint rule, in both themes.
- Light mint is rare and means "where you are" or "what's new"; status hues mean decisions.
- Capitals only in column heads and status stamps.
- One typeface, Albert Sans, with tabular figures everywhere.
- Flat tonal layers and 1px rules; shadow only for floating things.

## Colors

An evergreen-and-light-face board with one light-mint signal, links in the ink colour of each theme (so green means a decision, never a link), and a fixed set of status hues per theme.

### Primary
- **Evergreen** (evergreen): the ground of the dark theme, and the colour of text set on light face or mint there.
- **Evergreen Ink** (evergreen-ink): the ink of the dim theme, the column-head strip in dim, the selected row's outline in dim, and the fill of the primary button, picked chips, the bulk bar and the toast in dim. With Evergreen it is the board's own material in both themes.
- **Evergreen Strip** (evergreen-strip): the top strip in both themes and the column-head strip in dark; the darkest green, reserved for the board's header strips.
- **Light Face** (light-face): lettering on the backlit board: text in dark, top-strip text in both themes. In dark it is also the link and focus colour, so the backlit board has no second accent; the top strip's links and focus take it in both themes.

### Secondary
- **Light Mint** (light-mint): the 3px rule on the top strip (and the radar mark's dot and sweep inside it), the selected row's mark cell, the selected row's outline in dark, and the new-since-last-visit lamp in dark. Text on it is evergreen.
- **Printed Lamp Mint** (lamp-mint-print): the new-since-last-visit lamp in dim, a deeper mint with a thin evergreen ring (50% evergreen ink) so it reads on a light panel.

### Tertiary
- **Links and focus** use the theme's ink (evergreen ink in dim, light face in dark; the CSS custom property is still named `--lake`). A separate link green was dropped because it was too close to the Applied stamp. **Forest Soft** (forest-soft) is the fill of filters-in-use chips. The dim heat map steps through five mixes of evergreen ink into the panel (steps 1-3 take dark text, 4-5 light); dark uses five fixed evergreen steps, lightening as counts rise.
- **Status hues**, one per decision and one set per theme (the `-print` tokens are dim, the bare tokens dark): Saved amber, Applied green, Closed red, Not interested grey-green; Interviewing violet, Offer green and Rejected muted red serve the Applications pipeline. The same hue drives a job's stamp, its status dot and the wash of a decision button that's on. Not reviewed's status dot takes the muted text colour.

### Neutral
- **Sage** (sage), **Sage Panel** (sage-panel), **Sage Raised** (sage-raised), **Sage Sunken** (sage-sunken): the dim theme's ground, panels (filter rail, gate screen, controls), raised pills and sunken tags.
- **Evergreen Panel** (evergreen-panel), **Evergreen Raised** (evergreen-raised): the dark theme's panels and raised pills.
- **Moss Muted** (moss-muted) / **Light Face Muted** (light-face-muted): secondary text (company line, hints, size text, column heads in dark). **Printed Head Face** (head-face-print) is the column-head lettering on the evergreen strip in dim.
- **Sage Line** / **Evergreen Line**: 1px panel and control borders. **Row lines** (sage-row-line, evergreen-row-line) are a step quieter than panel lines, so the board's rows read as one surface.
- **Select wash** (mint-wash-print in dim, evergreen-select-wash in dark): the fill of the row you're on.

### Named Rules
**The Light Mint Rule.** Light mint appears in exactly three places: the top strip, the selected row's mark cell (and its outline in dark), and new-since-last-visit lamps. Never on buttons, chips, headings, charts or status. Forest green and the status greens are separate roles, not mint.

**The Printed Board Rule.** In dim the selected row is outlined in evergreen (2px inset), not mint: mint cannot hold an outline on a light panel. Its mark cell still turns mint, and the row takes the pale mint wash.

**The Stamp Hue Rule.** Saved is amber, Applied green, Closed red, Not interested grey-green. "Not reviewed" has no stamp and no hue on the board; an empty status cell is the unreviewed state.

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

Flat by default. Depth is tonal: ground, panel, raised and sunken steps of the same evergreen or sage, separated by 1px lines. The board itself has no shadow; the row you're on is marked by wash, a 2px inset outline and the mint mark cell, not by lifting.

### Shadow Vocabulary
- **Ambient** (`box-shadow: 0 1px 2px rgb(16 36 28 / 0.06), 0 4px 14px -6px rgb(16 36 28 / 0.14)` in dim; `0 1px 2px rgb(0 0 0 / 0.3), 0 6px 18px -8px rgb(0 0 0 / 0.55)` in dark): province tiles and the few card-like panels on other pages.
- **Floating** (`box-shadow: 0 8px 28px -10px rgb(0 0 0 / 0.45)`): the undo toast, the one element that floats over the board.

### Named Rules
**The Flat Board Rule.** Rows, heads and panels never cast shadows. State on the board is shown by fill, outline and stamp.

## Shapes

Gently squared controls (6px) for buttons, inputs, selects, tiles and the toast; 4px for keycaps and skeleton bars; 3px for tags; full pills for chips, filters in use and the session count. Board rows and panels are square-edged and run edge to edge, joined by 1px rules. Dots are round: the size dot scales with company size (an empty ring when unknown), the status dot sits before a status select, and the new lamp is 0.5rem.

## Components

### Buttons
Quiet, sentence-case controls that recede until needed.
- **Shape:** gently squared (6px), 1px line border, panel fill, 0.35rem by 0.8rem.
- **Primary:** lettering lit up: filled with ink, text in the ground colour, 700 weight (evergreen ink with sage text in dim; light face with evergreen text in dark and in the top strip).
- **Quiet:** transparent with muted text; gains the line border and panel fill on hover.
- **Hover / Focus:** border darkens to muted; focus is a 2px ink (evergreen in dim, light face in dark) outline at 2px offset. Colour transitions 0.18s ease.

### Decision buttons
The three decisions (Save S, Not interested X, Applied A), each with a line icon and, on the gate screen, its keycap. A decision that's on takes its status hue: a 22% wash of the hue, the full hue as border and icon colour, ink text. Pressing it again takes the job back to Not reviewed.

### Chips
- **Filter chips:** pill, control-line border at 3:1 against the panel, 0.85rem text, wrap inside the rail. On: filled with ink, ground-colour text.
- **Filters in use:** pill in forest soft with a small x that brightens on hover; each removes itself. Shown above the board so nothing filters silently.

### Inputs / Fields
- **Style:** 1px line border, panel fill, 6px radius, 0.35rem by 0.5rem. Placeholders in muted at full opacity. Checkboxes take the ink accent.
- **Focus:** the shared 2px outline.

### Navigation
The top strip: evergreen strip under a 3px light-mint rule, both themes, with its own backlit-board palette so controls in it read as lit. Brand mark (radar with a mint dot whose sweep turns only while a scan runs) and name at 800; nav links muted at 500, current page in light face at 650 with a 2px light underline that slides between links.

### Board row (signature)
The departure line. Head: evergreen strip, column labels in the label style. Row: tick box, mark cell, posted date, job title over the company line, place, level, size dot and text, status cell. Hover adds a 4% ink wash; ticked adds a 7% neutral wash; the row you're on takes the select wash, a 2px inset outline (evergreen in dim, mint in dark) and a mint mark cell with an evergreen chevron.

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
- **Do** outline the selected row in evergreen in dim and in mint in dark; turn its mark cell mint in both.
- **Do** colour a status the same everywhere it appears: stamp, dot and decision-button wash.
- **Do** keep the evergreen top strip and its mint rule in both themes.
- **Do** use tabular figures and Albert Sans for every surface.
- **Do** keep motion to the stamp, the gate screen's entrance and short colour transitions, and honour reduced motion.

### Don't:
- **Don't** use light mint outside the top strip, the selected row's mark cell and outline, and new-since-last-visit lamps.
- **Don't** set capitals anywhere but column heads and status stamps.
- **Don't** give Not reviewed a stamp or a hue on the board.
- **Don't** turn the board into cards or stacked blurbs, or move a row when its status changes.
- **Don't** cast shadows from rows, heads or panels.
- **Don't** add hover lifts or scattered hover effects on the board.
