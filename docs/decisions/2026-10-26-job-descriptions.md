# 2026-10-26: Full job descriptions for wanted roles

Replaces decision 5 of `2026-10-26-phase-2-scanning.md` ("descriptions only
where the list gives them").

Some jobs had no description in the app, so the user had to open the
posting. Missing (wanted roles, before): SmartRecruiters 136 of 136,
Workable 40/40, SuccessFactors search pages (EY) 33, Rippling 23/23,
BambooHR 13/13, Workday 22 (backlog).

- **Workable:** `?details=true` on the list request returns every
  description in the same response. No extra requests.
- **SmartRecruiters, Rippling, BambooHR, SuccessFactors search pages:** one
  detail request per job (`connectors/_common.fill_details`), only for:
  - roles `roles.toml` wants,
  - jobs that will be stored (in Canada),
  - jobs not already stored with a description;
  at most `[details] max_per_board` (60) per board per scan, with the usual
  pause. The rest follow on the next scan. A failed detail is a warning,
  never a failed board.
- **Workday:** its existing detail step is limited to wanted roles too.
- Breezy and Humi lists have no descriptions either; no wanted jobs were on
  them, so they aren't fetched.

A first version fetched details before the Canada filter, so foreign jobs
used up the per-board cap; fixed the same day.

Result after one scan: every system at 0 missing except SmartRecruiters,
whose three big boards (Ubisoft, Miratech, Sia) hit the cap and filled in on
the next scan.
