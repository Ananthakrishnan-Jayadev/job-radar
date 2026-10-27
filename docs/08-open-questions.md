# Open questions (to settle during planning)

> **Answered on 2026-10-26.** See
> [`decisions/2026-10-26-v1-scope-and-process.md`](decisions/2026-10-26-v1-scope-and-process.md).
> The "Facts still unverified" list at the end is still open; phases 2 and 4
> check them.

## Scope and product

1. **Exact target roles.** "AI engineer, data analyst etc.": which others?
   Data scientist, ML engineer, data engineer, BI developer, analytics engineer,
   MLOps? Which seniority (exclude senior, staff, manager, director)? Internships
   or new-grad roles?
2. **Locations.** All of Ontario, or specific cities (GTA, Waterloo region,
   Ottawa)? Include remote-in-Canada? Hybrid? Other provinces as a wider option?
3. **Work authorization or visa constraints** that should filter postings (some
   say "must be eligible to work in Canada"). Not discussed.
4. **Company size preferences.** The original criterion was employee count:
   which ranges (startup, mid-size, enterprise)? Is size a filter or a ranking
   factor?
5. **"Other features to make the experience better":** which of the ideas in
   06 are wanted for version 1?
6. **Tracking granularity:** track at the job level, the company level, or both?
   Which statuses?

## Process

7. **Agent rule:** should the coding agent only write files (as in
   `agentic_workday`), or may it run installs, tests and live probes?
8. **Plan format:** `PROJECT.md` + `TASKS.md` with phases (like
   `agentic_workday`)? Dated decision records (like the LinkedIn repo)?
9. **Git:** commit the research docs as the first commit? Use conventional
   commits? Create a GitHub repo or keep it local?

## Technical

10. **Interface for version 1:** web dashboard (needed for tracking), command line
    + CSV, or both? Add an MCP server later?
11. **Config format:** TOML or YAML (YAML matches `agentic_workday`)?
12. **Package manager:** `pip` + `venv` (`uv` isn't installed) or install `uv`?
13. **Scheduling:** cron or systemd timer for daily scans, or only on demand?
14. *Answered:* Adzuna's free tier is 25 calls in total, so it was used once
    and dropped (`decisions/2026-10-26-adzuna-snapshot.md`); Jooble not
    pursued. **Aggregator keys:** sign up for **Adzuna** (free app_id/app_key) and
    **Jooble**? Without them, finding new companies depends on the seed list and
    manual adds.
15. **Company size:** Wikidata only (free), or also a PDL or Apollo free-tier
    key? Manual entry always available?
16. **Job Bank CSV:** use it in version 1 or later? First check whether it
    includes employer names.
17. *Still open (2026-10-27):* companies on these and on Avature, Oracle
    Cloud and ADP were moved out of the database for now
    (`decisions/2026-10-27-company-cleanup.md`). **The Dayforce, iCIMS and Taleo gap:** accept it, cover it with aggregators,
    or allow a manual "add job by URL"?
18. **LinkedIn:** leave it out completely, or keep "open this search on LinkedIn"
    links (no automation)? Use the MCP server manually for size bands?
19. **Notifications:** daily digest by email or desktop notification?
20. **LLM features** (summaries or fit scores against a résumé) through local
    Ollama like `agentic_workday`, or none for now?

## Facts still unverified

- Rippling's page parameter name.
- ~~Whether Adzuna's `/top_companies` and Canada coverage work as documented.~~
  Not needed any more: Adzuna was dropped.
- Whether LinkedIn's company Jobs tab shows a total count (only relevant if
  LinkedIn is used).
- Whether Communitech/Prospect and MaRS boards have a usable feed (Getro or
  similar), which would be a great source of Ontario startups with jobs.
- The real Workday site names for Scotiabank and TELUS.
- Whether the ambiguous slug matches in 05 belong to the companies we think.
