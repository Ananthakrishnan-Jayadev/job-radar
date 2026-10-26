# Research material

## samples/
Real responses captured on 2026-10-26, one file per source. Each file is
`{"_request": {url, method, body}, "response": ...}`, and strings longer than 300
characters are cut. Useful as test fixtures and for writing parsers.

| File | Source |
|---|---|
| greenhouse_faire.json | Greenhouse Job Board API, `?content=true` |
| lever_wattpad.json | Lever Postings API (includes salaryRange in CAD) |
| ashby_wealthsimple.json | Ashby Posting API, `?includeCompensation=true` |
| smartrecruiters_canva.json | SmartRecruiters Posting API |
| workable_borrowell.json | Workable widget feed (Toronto jobs) |
| recruitee_bunq.json | Recruitee offers feed |
| breezy_demo.json | Breezy HR feed (vendor's demo account, fake data) |
| rippling_nesto.json | Rippling ATS board, paged (Canadian remote AI roles) |
| bamboohr_waabi.json | BambooHR careers list (a "Test" posting) |
| workday_sunlife_search.json | Workday search POST, "data scientist", including facets |
| workday_sunlife_detail.json | Workday job detail (exact startDate, additionalLocations) |

## scripts/
- `probe.py`: `python3 probe.py name1,name2,...` tries each name as a slug on
  nine job systems in parallel and prints the ones that answer with jobs.
- `shape.py`: prints the first job from each source (quick look at the shapes).
- `save_samples.py`: `python3 save_samples.py <out_dir>` re-captures `samples/`.

Only the Python standard library is needed. They run with plain `python3`.

## draft-code/
Written before the build was paused; reference only.
- `pyproject.toml`: proposed package (fastapi, uvicorn, httpx; `jobradar` CLI).
- `config.toml`: role profiles (AI/ML engineer, data analyst, data scientist)
  as include/exclude regexes plus server-side `search` terms, a global exclude
  list (director, VP, head of, chief, principal, manager), and `location_scope`.
- `models.py`: `Location` / `Job` dataclasses and the `in_scope` rule
  (Ontario = Ontario plus Canada-wide remote).
