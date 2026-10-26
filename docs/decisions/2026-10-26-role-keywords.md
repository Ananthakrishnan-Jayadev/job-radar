# 2026-10-26: Which roles to keep (roles.toml), for version 2

The user wants only roles in software development, data engineering and
analysis, and AI development and implementation. A fixed list of titles
doesn't work: companies name the same work differently ("AI Engineer",
"Forward Deployed Engineer", "Member of Technical Staff"), and keywords
alone are noisy ("engineer" also means civil or data-centre commissioning
engineers; "AI" appears in "Account Executive, AI"; "analyst" covers credit
analysts).

## How it was built

From the 6,941 distinct titles in the database (8,681 jobs, 450+
companies), in several rounds: draft include patterns per category, run
them over every title, read samples of what was kept, what was excluded and
what tech-sounding titles were missed, and adjust. French (Quebec) titles
are handled (développeur, analyste de données, apprentissage automatique...).

## The rules (roles.toml, explained at its top)

1. `exclude`: other job functions are out whatever else the title says
   (sales roles, account executives, recruiters, financial/mortgage/banking
   advisors, data entry, annotation, data-centre facility roles,
   technicians, mechanical/civil/FPGA/manufacturing engineers, designers,
   animators, editors...). They match job *functions*, not domain words:
   "Salesforce Developer" and "Manager, Mortgage Pricing Analytics" stay.
2. Three categories, on by default: **software**, **data**, **ai**.
   An AI-only title must also name a role (`ai_role`), so "AI Growth Ops" is out.
3. `soft` words (risk, audit, governance, strategy, product/program manager,
   privacy...) send a title to **adjacent** unless a `strong` builder role
   (engineer, developer, scientist, architect...) is also there.
4. **adjacent** is off by default: business/systems analysts, IT support,
   product owners, technical consultants, implementation specialists, data
   governance, network engineers. The user decides whether to turn it on.

## Result on 2026-10-26 data

| | Titles | Open jobs |
|---|---|---|
| Kept (software / data / ai) | 2,002 of 6,941 | 2,539 of 8,877 (28%) |
| Adjacent (off) | 272 | |
| Excluded by a rule | 1,195 | |
| No match | 3,472 | |

No job the user had saved or applied to would be dropped.

`jobradar/roles.py` reads the file; `tests/test_roles.py` pins 60 real
titles (wanted, unwanted, adjacent). The rules matched the tuning draft on
all 6,941 titles. Not yet wired into scanning or search: that's a version 2
choice (filter when storing, or hide by default in the UI).
