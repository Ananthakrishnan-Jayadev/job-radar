# 2026-10-26: Researching careers pages for imported companies

Two lists of companies were added without job boards: the user's
`joblst.xlsx` (108 companies, see `2026-10-26-import-company-lists.md`) and
the employers from the one-time Adzuna snapshot (327, see
`2026-10-26-adzuna-snapshot.md`). The app's own `find-boards` can only read
careers links and guess board names, so web research filled the gap.

## How

1. `find-boards` first (no cost beyond requests): careers links, careers
   pages, then name guesses (whole names only; first-word guesses matched
   other companies, e.g. "Block 64" -> Block Inc.).
2. Then web-search agents for whatever was left, in batches of about 30,
   each company given a hint (city and a job title) to disambiguate. They
   reported: website, careers page, the job board behind it, a status
   (found / staffing or job site / acquired or renamed / no careers page /
   closed / unsure), duplicates within the batch, and a one-line note.
   Guessed boards were sent for verification too.
3. A one-off script applied the results (after a database backup).

## Rules used when applying

- A board found from a careers page is added **confirmed and switched on**.
- A board that belongs to a **new parent company** (acquisitions such as
  Advanced Utility Systems -> Harris Computer, Street Contxt -> BlueMatrix,
  eCompliance -> Veriforce) or that lists a **whole parent group's jobs**
  (Activision Blizzard -> Xbox Gaming, Oliver Wyman -> Marsh McLennan) is
  added **switched off**, with a note; turning it on shows the parent's
  Canadian jobs under the listed name.
- **Staffing agencies, recruiters and job sites** are marked company status
  `ignored` (their jobs leave the default list; reversible). One employer
  that couldn't be found anywhere and posted AI roles from a "supplies"
  business (Urban Ridge Supplies) was ignored as possibly fake.
- **Duplicates** are merged into one company: name variants (PwC / PwC
  Canada), legal names (TD Bank Group -> TD Bank), and companies whose board
  is already on the list (Reonomy -> Altus Group, Octopusapp -> Jobber).
  Snapshot jobs at a company already scanned from its own board are dropped.
- **SuccessFactors sites** live on the company's own domain, so the research
  tagged them explicitly (Deloitte, EY, Hydro One, Rogers, Teck); a page check
  confirmed Hydro One. Magna's old-style Workday address
  (`wd3.myworkdaysite.com/recruiting/magna/Magna`) was rewritten to the
  standard form and checked.
- Every researched company's notes start with "Careers research
  (2026-10-26): <status>. <evidence>". Findings marked "unsure" are leads,
  not facts.

## Results

- joblst.xlsx: 33 of 108 companies scanned from a real board; 11 more have
  boards on systems the app can't read.
- Adzuna employers: 127 scanned from a real board (84 found by research,
  11 name guesses verified, 32 guesses still unconfirmed); 50 ignored as
  staffing or job sites; 23 duplicates merged; 37 on unreadable systems
  (mostly Oracle Recruiting, iCIMS, ADP, UKG, Dayforce, Gem).

The agents' raw reports were not kept in the repository; the useful part of
each is in the company's notes.
