# Canada- and Ontario-specific sources

## The problem the user raised

> "im looking for opportunities filtered down to canada and ontario, i couldnt find
> a website that have canada info that much, most of the sites are US companies heavy"

Most company-data products are US-heavy. Two points that help:

1. **Many US-heavy tools still filter to Canada.** Apollo and People Data Labs are
   global and filter by country = Canada, region = Ontario and employee range.
   Coverage is good from about 50 employees up and thinner for small companies.
   The job-system feeds in `03-data-sources.md` are global too: they return every
   job with a location field, so filter for Ontario afterward.
2. **Canada-specific sources exist**, below.

## Canadian sources

| Source | What it gives | Access | Notes |
|---|---|---|---|
| **Job Bank open data** (Employment and Social Development Canada) | Every posting on Canada's national job board | Free, monthly CSV (English and French), Open Government Licence – Canada | See below |
| **Job Bank website** | Live search, `https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=python&locationstring=Ontario&fage=2` | Website (returned HTTP 200) | No official live API found. A third-party Apify scraper exists; don't use it. Use the CSV. |
| **Eluta.ca** | Canadian job search engine that collects jobs from employers' own career sites | Website | From general knowledge, not checked this session. Good for counting active postings per employer. No API known. |
| **Canada's Top 100 Employers / Greater Toronto's Top Employers / other regional lists** (Mediacorp, canadastop100.com) | Employer profiles with employee counts | Free to read | A ready-made shortlist of established employers; useful seed list. |
| **Communitech "Work In Tech" / Prospect** | Jobs at startups and scale-ups, mostly in Ontario (Waterloo region) | Website | Communitech took over Prospect ("Canada's largest startup job board"). It stays free for job seekers. Platform and API not confirmed. |
| **MaRS Discovery District job board** | Toronto's fast-growing startups | Website; only members can post | The companies listed are already screened. Filters and platform not confirmed. |
| **Scott's Directories** | Canadian business database with employee counts and industry codes, filterable by province and city | **Paid** | Its public pages show employee counts. Strong for manufacturing and traditional industries. |
| **Statistics Canada, Canadian Business Counts** | Business counts by industry and size range per region | Free | Totals only, no individual companies; useful for market context, not shortlisting. |
| **Talent.com** (founded in Montreal) | Large job aggregator, strong in Canada | Partner or publisher programs | Not tested. |
| **Adzuna Canada** | Job search API with Canada coverage (`/jobs/ca/...`) | Free developer key | **The best way to find which companies are hiring in Ontario.** See 03. |
| **Jooble** | Job search API, covers Canada | Free key on request | See 03. |
| **Government jobs**: GC Jobs (federal, jobs-emplois.gc.ca), Ontario Public Service (gojobs.gov.on.ca), cities such as Toronto, Ottawa, Mississauga | Public-sector data and analyst roles | Websites (some offer RSS) | Not investigated; government is a big employer of data analysts in Ontario. |
| **Vector Institute** (Toronto AI institute) | AI research and engineering roles, plus a sponsor list of AI-active companies | Website | The "vector" Ashby board **may or may not** be the Vector Institute (see 05). |

### Job Bank open data in detail

- Dataset: **"Job Postings Advertised on Canada's National Job Bank Website"**,
  <https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072>
- Monthly CSV files, in English and French. Last update seen through a mirror:
  April 2026. Check the portal for the latest month.
- Two kinds of rows:
  - **direct postings** (employers post on Job Bank): job code (NOC), industry
    code (NAICS), work location, **number of vacancies**, salary and benefits,
    hours, requirements, employment terms
  - **partner postings** (private and provincial job boards sending XML feeds):
    fewer fields (title, NOC, location, salary, hours, terms)
- `NA` means not available.
- Whether **employer names** appear in every row is not confirmed. Check one CSV
  before relying on it to find companies.
- Leans toward non-tech and immigration-related postings (for example LMIA
  employers). Use it to see who is hiring in Ontario, not as a live feed: it's
  about a month behind.
- Mirror: `donnees.iriu.ca/dataset/ea639e28-...`

## Where Canadian employers post jobs (from testing)

- **Toronto, Waterloo and Ottawa startups and scale-ups:** mostly **Ashby**, then
  Lever and Greenhouse (see 05).
- **Banks and insurers:** **Workday**. TD, RBC, CIBC, BMO, Sun Life and Manulife
  were all confirmed. Scotiabank's site name is still to find.
- **Many mid-size and traditional Canadian employers:** **Dayforce** (no public
  feed), iCIMS, Taleo, SuccessFactors. These are **gaps** to cover with
  aggregators (Adzuna), Job Bank, or a manual look-up.

## Location parsing: needed for any Canadian source

The location parser decides whether a job is Ontario, Canada-remote or
elsewhere. Forms seen or expected:

- `"Toronto, Ontario"`, `"Toronto, ON"`, `"Toronto, ON, Canada"`,
  `"TORONTO-Ontario-Canada"` (from a Workday link), `"Toronto-Ontario"`,
  `"Toronto Headquarters"` (Ashby; its address field holds the region)
- `"GTA"`, `"Greater Toronto Area"`, `"Kitchener-Waterloo"`, `"KW"`,
  `"Ottawa / Hybrid"`, `"Remote – Canada"`, `"Remote (Canada)"`, `"Canada"`
  (Rippling, remote)
- French: `"Montréal, QC"`, `"Québec"`, `"Ingénieur IA Appliquée"` (French
  titles from Quebec employers on Rippling)
- Several places: Greenhouse `"New York City, NY; San Francisco, CA"`, Workday
  `"2 Locations"` (fetch the detail for `additionalLocations`)
- Ambiguous: `"London"` (Ontario or UK), `"Waterloo"` (Ontario, Iowa or
  Belgium), `"Hamilton"` (Ontario or New Zealand), `"Windsor"`,
  `"Cambridge"` (Ontario or the UK and US ones), `"Richmond"` (BC or US),
  `"Kingston"` (Ontario or Jamaica). Use the country and province fields when
  present, and default to Canada only when the company is Canadian.
- Province codes: ON, QC, BC, AB, MB, SK, NS, NB, NL, PE, YT, NT, NU.
- Ontario cities to recognise without a province: Toronto, Mississauga,
  Brampton, Markham, Vaughan, Richmond Hill, Oakville, Burlington, Hamilton,
  Kitchener, Waterloo, Cambridge, Guelph, London, Ottawa, Kanata, Kingston,
  Windsor, Barrie, Oshawa, Whitby, Pickering, Ajax, Milton, St. Catharines,
  Niagara Falls, Sudbury, Thunder Bay, Peterborough.
- Rule drafted earlier: **"ontario" scope = Ontario jobs plus remote jobs open
  across Canada** (country CA, remote, no province). **"canada" scope = anything
  with country CA.** See `research/draft-code/models.py` (`in_scope`).
