# 2026-10-27: Board review and keeping only scannable companies

**Board review.** 61 companies had only a board guessed from their name.
- Each guess was checked against the Adzuna snapshot: if a job Adzuna listed
  for the company is on the guessed board, the guess is right (34 proven
  this way).
- The user checked the rest. Wrong guesses replaced with the user's links:
  - Sonder → Workday `sonder.wd1/Join_Sonder`;
  - Fable → Workable `fable-1`;
  - Maple → Lever `getmaple`;
  - Lightspeed → Ashby `lightspeedhq`.
- Uber's careers site (`jobs.uber.com`) can't be read; its SmartRecruiters
  guess was wrong.
- Xanadu and Helcim turned out to use HiBob (`2026-10-27-hibob.md`).
- Workday boards added from the user's links: Citi (`citi.wd5/2`), CI
  Financial. McKesson, IQVIA and Blue Origin were guessed (their careers
  sites are Radancy front ends) and confirmed by a scan; Blue Origin lists
  no Canadian locations.

**Cleanup.** The user decided 200+ scannable companies is enough for now.
- **Removed:** the 244 companies without an enabled job board of their own:
  - 174 Adzuna-only employers (including 50 marked ignored: staffing
    agencies, job sites);
  - 75 from the user's own lists (acquired, closed, not hiring, no job
    system);
  - 11 whose boards were switched off (parent-company boards, Teck, Uber).
- **None had any tracking** (status, notes, applied date).
- **Kept in** `data/removed-companies-20261027-010534.db` (same schema, only
  those companies, with their boards, jobs and research notes) and a `.csv`
  list. A full backup was taken first.
- Uber was taken out of `seeds/companies.toml` so `jobradar seed` doesn't
  bring it back. Re-importing `joblst.xlsx` would bring some back.

Result: 215 companies, every one with a confirmed board.

**Still unreadable,** for a later connector if wanted (companies, wanted jobs
at the time):
- iCIMS: Kinaxis, BDO, FGF Brands, Porter... (7, 18 jobs);
- Avature: National Bank, lululemon... (6, 15);
- Oracle Cloud (7, 11);
- ADP (5, 11);
- Gem (3);
- UKG, Eightfold, Phenom, Dayforce (2–3 each).

Details are in the removed-companies notes.
