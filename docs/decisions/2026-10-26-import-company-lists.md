# 2026-10-26: Importing the user's own company lists

The user brought `joblst.xlsx`: 108 small Canadian AI and software companies
(sheet LIST with links; sheet Sheet1 with tiers and sizes like "Xello (51-200)").

- **No new package.** `.xlsx` is zipped XML; `jobradar/importer.py` reads it
  with the standard library (shared strings, inline strings, several sheets).
  `.csv` works too.
- **What counts as a careers link:** the first real web link in a row. Google
  search and LinkedIn search/company links are skipped; in this file only 9
  of 108 rows had a real link.
- **Sizes from ranges** use the middle of the range ("51-200" stores 125,
  shown as the 50-199 band) under a new size source, `imported`, ranked
  between stillhiring.today and Wikidata. Migration 4 dropped the database
  CHECK on `size_source` (validated in `enrich.PRIORITY` instead) so new
  sources don't need another table rebuild.
- **Tiers go into notes** ("From joblst.xlsx: TIER A: Two lists / A1. ...").
- **Finding careers pages without a search engine.** The app can't search
  Google (against its terms, and blocked quickly). `find-boards` reads the
  careers link where there is one, then tries the company's name on nine job
  systems. A board found from a link or careers page is added confirmed; one
  found by name alone is added **unconfirmed**, since names collide, and only
  if it has jobs in Canada.
- The user's database was backed up before the first real import
  (`data/jobradar-backup-*.db`).
