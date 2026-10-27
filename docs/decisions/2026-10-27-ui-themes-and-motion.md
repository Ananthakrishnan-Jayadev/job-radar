# 2026-10-27: Dim and dark themes, Tailwind and motion

Updates `2026-10-26-react-ui.md` ("plain CSS, minimal UI dependencies"). The
user asked for cosmetic improvements: "real libraries", Tailwind,
animations, and a dim light look instead of full dark, or a switch.

- **Themes:** two, on `<html data-theme>`. A sun/moon button in the top bar
  switches them, remembered in the browser; a script in `index.html` applies
  it before the first paint.
  - **dim** (default): a low-glare grey-green light (`#dde3e1` background).
  - **dark:** spruce-night slate (`#121a1d`), not black.
  - Same identity as before: lake blue for actions, amber only for "new"
    and for selections.
- **Libraries** (versions checked against React 18 and Vite 5):
  - `tailwindcss` 4 with `@tailwindcss/vite`;
  - `motion` 14 (animations);
  - `lucide-react` (icons);
  - `@number-flow/react` (animated numbers);
  - `@fontsource-variable/instrument-sans` (the font, now self-hosted).
  - Tailwind 4 needs Node 20+.
- **Tailwind without its reset (preflight).** The existing pages rely on
  normal paragraph and list spacing. The app's own styles sit in the
  components layer so utilities can override them. Theme colours are
  Tailwind colours too (`bg-surface`, `text-muted`...).
- **Motion:**
  - page cross-fades (not on filter changes);
  - a sliding highlight in the menu;
  - job rows that ripple in, and shimmer placeholders while loading;
  - rolling counts;
  - springy province tiles and chips;
  - an animated "More filters";
  - a spring scan progress bar;
  - a radar sweep in the logo while a scan runs.

  `MotionConfig reducedMotion="user"` and a CSS rule turn all of it off when
  the system asks for reduced motion.
- **From the user's screenshots, same day:**
  - The page is now up to 1,880px wide (was 1,500px, leaving ~210px empty on
    each side of a 1080p screen).
  - Filter chips wrap instead of pushing the sidebar sideways.
  - Switched-off Adzuna boards are hidden in the companies list.
  - The province map is a heat map of the **ten provinces in a 5 × 2 grid**,
    west to east (BC AB SK MB ON / QC NB NS PE NL). The territories had no
    jobs and made it lopsided; their jobs still count in "all of Canada".
    Empty provinces are dashed outlines, and tiles can't be text-selected.
- **Not adopted:** 21st.dev (component source and prompts need an account
  and API key) and the taste-skill plugin (made for new showpiece pages).
  For visual review the user sends screenshots: only Firefox is installed,
  and the browser tool here works with Chrome only.
