# Data sources: tested job and company data access

Every endpoint marked **✅ tested** was called live on **2026-10-26** and returned
real data. A real response from each is in [`research/samples/`](research/samples/),
with long descriptions cut to 300 characters. Re-fetch them with
`python3 docs/research/scripts/save_samples.py docs/research/samples`.

## Contents

1. Why LinkedIn and Composio are not the answer
2. Company job systems (applicant tracking systems): per-company feeds
3. Job-search aggregators: searching across companies
4. Company size (employee count) sources
5. Detecting which job system a company uses
6. Access rules and etiquette

---

## 1. Why LinkedIn and Composio are not the answer

**LinkedIn** forbids scraping and automating its website (its User Agreement), and
forbids calling its private internal API. Tools like the LinkedIn MCP server
(see 02) work by driving the user's own logged-in browser. That works, but it
breaks the terms and puts the account at risk.

**Composio** (and similar platforms) is not exempt. It uses LinkedIn's **official
public developer API** through OAuth2: someone registers an app in LinkedIn's
developer portal, the user signs in and grants permissions (scopes), and the
platform calls the official endpoints. Composio's docs confirm OAuth2 only (no
bearer tokens). Personal scopes are available by default; organization and ads
scopes need app approval, and without them organization actions fail with 403.
If any requested scope isn't enabled for the app, LinkedIn rejects the whole
OAuth request.

What the public LinkedIn API allows without a special partner agreement:
- your own basic profile (sign-in data: name, email, photo)
- publishing posts as yourself, and as a company page if you're an admin with
  the right access
- ads and company-page management (marketing APIs, approval needed)

What it does **not** allow: reading other people's profiles, searching people or
companies, searching or reading jobs, the inbox or messages, employee counts or
job counts for arbitrary companies. LinkedIn keeps that data for paid partner
programs (Talent Solutions, Sales Navigator) and its own products.

→ **Composio cannot help with company shortlisting.** Hosted services that can
(Cadenza and Unipile, the LinkedIn MCP's sponsors) drive real signed-in sessions,
so they carry the same terms-of-service risk.

Sources: <https://docs.composio.dev/kb/guide/toolkits-linkedin>,
<https://composio.dev/auth/linkedin>, <https://docs.composio.dev/docs/controlling-scopes>,
<https://docs.composio.dev/docs/custom-app-vs-managed-app.md>

---

## 2. Company job systems: per-company feeds

Most companies run their careers page on a hosted applicant tracking system.
Many of these systems expose the company's open jobs as public JSON, because they
exist to be shown on the company's own site. **One request per company returns
all its open jobs.**

### Summary

| System | Official public? | Login | Tested | Typical users |
|---|---|---|---|---|
| Greenhouse | ✅ Job Board API | No | ✅ | Tech, mid to large |
| Lever | ✅ Postings API | No | ✅ | Tech startups, scale-ups |
| Ashby | ✅ Posting API | No | ✅ | Newer startups (very common in Toronto tech) |
| SmartRecruiters | ✅ Posting API | No | ✅ | Mid to large, retail, hospitality |
| Workable | Public widget feed | No | ✅ | Small and mid-size companies |
| Recruitee | Public careers feed | No | ✅ | Small and mid-size companies, startups |
| Breezy HR | Public careers feed | No | ✅ | Small companies |
| Rippling ATS | Public board feed | No | ✅ | Growing startups |
| BambooHR | ❌ Undocumented careers JSON | No | ✅ | Small companies |
| Workday | ❌ Undocumented careers JSON | No | ✅ | **Banks, insurers, telecoms, large enterprises** |
| Personio | Public XML feed | No | ✅ | Mostly European companies |
| Dayforce | No known public feed | – | ❌ | Common with Canadian employers (founded in Toronto) |
| SAP SuccessFactors (Career Site Builder) | Public job feed at `/sitemap.xml` | No | ✅ | **Large enterprises, e.g. Scotiabank** |
| JazzHR | Public XML job feed | No | ✅ | Small companies (careers pages at `*.applytojob.com`) |
| iCIMS / Taleo (Oracle) | No public feed | – | ❌ | Large enterprises |
| Jobvite, JazzHR, Teamtailor, Pinpoint, Comeet | Not investigated | – | – | – |

### Greenhouse ✅ official

- **List:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`
  - `?content=true` adds the description (`content`, HTML-escaped), `departments`
    and `offices`.
- **One job:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{id}`
- **Response:** `{jobs: [...], meta: {total}}`. Job fields: `id`, `title`,
  `absolute_url`, `location.name` (free text, may list several places separated
  by `;`, for example `"New York City, NY; San Francisco, CA"`), `updated_at`,
  `first_published` (ISO, use this as the posted date), `company_name`,
  `requisition_id`, `internal_job_id`, `metadata[]` (custom fields, for example
  Employment Type), `language`, `application_deadline`.
- No paging; all jobs come in one response (Databricks returned 895).
- `board_token` is the slug in `boards.greenhouse.io/{token}` or
  `job-boards.greenhouse.io/{token}`.
- The fuller **Harvest API** needs an employer key, so it's not usable.
- Tested: airbnb (191 jobs), faire, databricks, stripe and others.

### Lever ✅ official

- **List:** `GET https://api.lever.co/v0/postings/{company}?mode=json`
  (supports `&limit=`, `&skip=`, and filters like `&location=`, `&team=`,
  `&department=`, `&commitment=`).
- **Response:** a JSON array. Fields: `id`, `text` (the title), `hostedUrl`,
  `applyUrl`, `createdAt` (**milliseconds since epoch**), `country` (ISO, for
  example `"CA"`), `workplaceType` (`hybrid` | `remote` | `onsite` |
  `unspecified`), `categories {location, allLocations[], team, department,
  commitment}`, `salaryRange {min, max, currency, interval}` (when published,
  for example Wattpad: 140000–180000 CAD per year), plus description fields
  (`descriptionPlain`, `lists`, `additionalPlain`, ...).
- There is also an EU instance, `api.eu.lever.co`, for EU-hosted accounts.
- Tested: wattpad, pointclickcare, waabi, waveapps, d2l, and leverdemo (the
  vendor's demo account).

### Ashby ✅ official

- **List:** `GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true`
- **Response:** `{jobs: [...], apiVersion}`. Fields: `id`, `title`,
  `department`, `team`, `employmentType` (`FullTime`...), `location` (text, for
  example "Toronto Headquarters"), `secondaryLocations[]`, `publishedAt` (ISO),
  `isListed`, `isRemote`, `workplaceType` (`OnSite` | `Hybrid` | `Remote`),
  **`address.postalAddress {addressLocality, addressRegion, addressCountry}`**
  (structured: `"Toronto" / "Ontario" / "Canada"`, the best location data of any
  source), `jobUrl`, `applyUrl`, `descriptionHtml`, `descriptionPlain`.
- With `includeCompensation=true`: `compensation.compensationTierSummary` (for
  example `"CA$116K – CA$145K • Offers Equity"`), `scrapeableCompensationSalarySummary`,
  and `compensationTiers[]`.
- Tested: wealthsimple (42), cohere (116), snowflake (353) and more.

### SmartRecruiters ✅ official

- **List:** `GET https://api.smartrecruiters.com/v1/companies/{companyId}/postings?limit=100&offset=0`
  (paged; `totalFound` gives the total). It also accepts query filters (for
  example `q=`, `country=`, `city=`); check the docs before relying on them.
- **One job:** the `ref` field, for example
  `https://api.smartrecruiters.com/v1/companies/canva/postings/{id}`.
- **Public page:** `https://jobs.smartrecruiters.com/{Company}/{id}` (returned
  HTTP 200 when tested).
- Fields: `id`, `name` (the title), `uuid`, `refNumber`, `releasedDate` (ISO),
  `location {city, region, country (lowercase ISO, for example "ca"), remote,
  hybrid, fullLocation}`, `department`, `function {id, label}`,
  `experienceLevel {id, label}` (for example `mid_senior_level`),
  `typeOfEmployment`, `industry`, `customField[]`, `company {identifier, name}`.
- **Warning:** postings can be very old. Hootsuite's sample was released in 2017.
  Filter by `releasedDate`.
- Tested: smartrecruiters, canva (95), hootsuite, uber (1).

### Workable ✅ (public widget feed)

- **List:** `GET https://apply.workable.com/api/v1/widget/accounts/{subdomain}`
- **Response:** `{name, description, jobs: [...]}`. Job fields: `title`,
  `shortcode`, `url` (`https://apply.workable.com/j/{shortcode}`),
  `application_url`, `published_on` and `created_at` (dates), `country`, `state`,
  `city`, `telecommuting` (remote, true/false), `department`, `function`,
  `industry`, `employment_type`, `experience`, `education`, and
  `locations[] {country, countryCode, region, city, hidden}`.
- The v3 endpoint (`POST /api/v3/accounts/{x}/jobs`) returned "Not Found" when
  tried; use v1.
- Tested: huggingface, borrowell (Toronto, 2 jobs), 1password (1).

### Recruitee ✅

- **List:** `GET https://{company}.recruitee.com/api/offers/`
- **Response:** `{offers: [...]}`. Fields: `id`, `slug`, `title`, `careers_url`,
  `careers_apply_url`, `status`, `published_at`, `created_at`, `updated_at`,
  `close_at`, `city`, `state_name`, `state_code`, `country`, `country_code`,
  `postal_code`, `remote`, `hybrid`, `on_site`, `locations[] {city, state,
  state_code, country, country_code}`, `salary {min, max, period, currency}`,
  `department`, `employment_type_code`, `experience_code`, `education_code`,
  `tags`, `description`, `requirements`, `company_name`.
- Tested: bunq. The company "recruitee" itself returned `{"error":"Not Found"}`,
  so not every company uses its own name as the slug.

### Breezy HR ✅

- **List:** `GET https://{company}.breezy.hr/json`
- **Response:** a JSON array. Fields: `id`, `friendly_id`, `name` (the title),
  `url`, `published_date`, `type {id, name}`, `department`, `salary` (text, for
  example `"$0.05 – $0.06 / hour"`), `location {name, city, state {id, name},
  country {id, name}, is_remote, primary}`, `locations[]`, `company {name,
  friendly_id}`.
- Tested: breezy (the vendor's demo account, fake data).

### Rippling ATS ✅

- **List:** `GET https://ats.rippling.com/api/v2/board/{company}/jobs`
- **Response:** `{items: [...], page, pageSize (20), totalItems, totalPages}`, so
  it is **paged**; check the page parameter (probably `?page=N`) before relying
  on it. Item fields: `id`, `name` (the title, sometimes with extra whitespace,
  and in French for Quebec employers), `url`, `department.name`, `language`,
  `locations[] {name, country, countryCode, state, stateCode, city,
  workplaceType ("REMOTE" ...)}`.
- No posted date in the list.
- Tested: rippling, nesto (39 items, including "Senior Applied AI Engineer",
  remote in Canada).

### BambooHR ⚠️ undocumented

- The official API needs the **employer's** API key, so it's not usable.
- **List:** `GET https://{company}.bamboohr.com/careers/list` →
  `{meta: {totalCount}, result: [...]}`. Fields: `id`, `jobOpeningName`,
  `departmentId`, `departmentLabel`, `employmentStatusLabel`, `employmentType`,
  `location {city, state}`, `atsLocation {country, state, province, city}`,
  `isRemote`, `locationType`.
- **One job:** `GET https://{company}.bamboohr.com/careers/{id}/detail` →
  `result.jobOpening {jobOpeningShareUrl, jobOpeningName, jobOpeningStatus,
  location {city, state, postalCode, addressCountry}, ...}`.
- **Public page:** `https://{company}.bamboohr.com/careers/{id}`
- A company that doesn't use BambooHR **redirects (302) to `https://www.bamboohr.com/`**.
  Treat that as "not found". zapier returned an empty list; waabi returned one
  posting titled "Test" in San Francisco, so filter out obvious test postings.
- Undocumented, so it can change without notice. Mostly used by smaller
  companies.

### Workday ⚠️ undocumented, and the most important one for Canadian enterprises

- Careers site URL: `https://{tenant}.wd{N}.myworkdayjobs.com/{site}` (also
  `/en-US/{site}`). `N` varies (wd1, wd3, wd5...), so store the full URL per
  company.
- **Search:** `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
  with headers `Content-Type: application/json`, `Accept: application/json` and
  body
  ```json
  {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "data scientist"}
  ```
  - **`limit` is at most 20**; page through with `offset`.
  - **`searchText` searches on Workday's side**, so search each target role
    instead of downloading thousands of postings (TD 1,126, RBC 820, BMO 702).
  - Response: `{total, jobPostings: [{title, externalPath, locationsText,
    postedOn, bulletFields: [reqId]}], facets: [...]}`.
  - `locationsText` can be `"2 Locations"` instead of a place. The first
    location is in `externalPath`, for example `/job/Toronto-Ontario/Data-Scientist_JR00128241`.
  - `postedOn` is relative ("Posted Today", "Posted 2 Days Ago", "Posted 30+ Days Ago").
  - `facets` includes **`Location_Country`** (for example Canada, with an `id`
    and `count`), `jobFamilyGroup`, `jobFamily` and others. Filter on Workday's
    side with `"appliedFacets": {"Location_Country": ["<canada id>"]}`; the id
    differs per tenant, so read it from a first response.
  - `total` is reliable on the first page; some reports say it can read 0 on
    later pages, so read it from offset 0.
- **One job:** `GET https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{externalPath}`
  → `jobPostingInfo {title, location ("Toronto, Ontario"), additionalLocations
  ["Waterloo, Ontario"], startDate ("2026-10-23", the actual posting date),
  postedOn, timeType, jobReqId, externalUrl, country {descriptor, id},
  remoteType, jobDescription}`, plus `hiringOrganization` and `similarJobs`.
  Fetch details only for jobs that matched a role, to get the exact date and all
  locations.
- **Public page:** `jobPostingInfo.externalUrl`, or
  `https://{tenant}.wd{N}.myworkdayjobs.com/{site}{externalPath}`.
- Tested working: `td.wd3/TD_Bank_Careers`, `rbc.wd3/RBCGLOBAL1`,
  `cibc.wd3/search`, `bmo.wd3/External`, `sunlife.wd3/Experienced-Jobs`,
  `manulife.wd3/MFCJH_Jobs`, `nvidia.wd5/NVIDIAExternalCareerSite`.
- `scotiabank.wd3/External` and `telus.wd3/TELUS` returned **HTTP 422**. For
  Scotiabank the reason turned out to be that it isn't on Workday at all (see
  SAP SuccessFactors below). TELUS is still to check.
- Be gentle: 20 per page, a short pause between pages, search per role.
- Related: the user's `agentic_workday` project already automates Workday
  application pages (see 07).

### SAP SuccessFactors ✅ (added 2026-10-26)

- Career sites built with SuccessFactors' "Career Site Builder" live on the
  company's own domain, e.g. `https://jobs.scotiabank.com`. Recognize them by
  assets from `rmkcdn.successfactors.com` or a `j2w.init(` script in the page.
- **List:** `GET {site}/sitemap.xml`. Despite the name it's an RSS 2.0 feed of
  **every** open job, with Google job fields: `title` ("Software Engineer
  (Toronto, ON, CA)"), `link`, `guid`, `g:id`, `g:location` ("Toronto, ON,
  CA"), `g:job_function`, `g:employer`, `g:expiration_date`, and the full
  `description` (HTML-escaped).
- No posting date in the feed (only an expiry date).
- Can be large: Scotiabank's was 38 MB for 1,471 jobs, almost all of it base64
  images inside descriptions.
- Not usable: the keyword RSS (`/services/rss/job/?keywords=...`) returns only
  20 items and matches description text. The HTML search pages
  (`/search/?q=&locationsearch=`, 25 per page) work but need many requests.
- Tested: Scotiabank (1,471 jobs; 1,060 in Canada; 682 in Ontario, matching
  the site's own Ontario search). Details in
  `docs/decisions/2026-10-26-successfactors.md`.

### JazzHR ✅ (added 2026-10-26)

- Careers pages live at `https://{company}.applytojob.com/apply` (HTML).
- **List:** `GET https://app.jazz.co/feeds/export/jobs/{company}`: XML for job
  sites, `<jobs><company/><job>…</job></jobs>`. Job fields: `id`
  (`job_YYYYMMDDhhmmss_…`, the creation time), `status` (Open), `title`,
  `department`, `url`, `city`, `state` (province code), `country` (name),
  `postalcode`, `description` (HTML), `type` (Full Time…), `experience`.
- Unknown company: 404 with an empty body.
- Quirk: the city field can hold "Remote – Canada & United States" or
  "Remote/Toronto"; read as remote (keeping a real city if one is named).
- Not usable: `{company}.applytojob.com/apply/jobs/feed` (404).
- Tested: Xello (3 jobs), Apertera, formerly Alexa Translations (26 jobs,
  in Canada and abroad).

### Personio ✅ (mostly European companies)

- `GET https://{company}.jobs.personio.de/xml` → XML `<workzag-jobs><position>`
  with `id`, `subcompany`, `office`, `additionalOffices`, `department`, and more.
- Only useful for European companies with Canadian offices.

---

## 3. Job-search aggregators: searching across companies

These answer "who is hiring for X in Ontario?" across all companies. Use them to
**find companies**, then check each company's own feed.

| Source | Access | Canada | Tested |
|---|---|---|---|
| **Adzuna API** | Free developer key (app_id + app_key) from developer.adzuna.com | ✅ `/v1/api/jobs/ca/search/{page}` | Endpoint exists; without a key it returns `{"exception":"AUTH_FAIL"}`. **Needs a key to go further.** |
| **Jooble API** | Free key on request (`POST https://jooble.org/api/{key}`) | ✅ | Without a key, blocked by a Cloudflare check. Needs a key. |
| **Job Bank** (Government of Canada) | Free open data, monthly CSV | ✅ | Dataset confirmed (see 04) |
| Careerjet | Publisher API (affiliate) | Has Canada | Not tested |
| Talent.com (founded in Montreal) | Partner or publisher programs | Strong in Canada | Not tested |
| Indeed | Its public publisher API was **discontinued**; don't plan on it | – | – |
| TheirStack, Lightcast | Paid job-data products with Canadian coverage | ✅ | Not tested (paid) |

**Adzuna details** (from its public docs; confirm once there's a key):
`GET https://api.adzuna.com/v1/api/jobs/ca/search/1?app_id=..&app_key=..&what=data%20analyst&where=Ontario&results_per_page=50&max_days_old=14&sort_by=date`
→ `results[] {id, title, description (snippet), company.display_name,
location.display_name, location.area ["Canada","Ontario","Toronto"], created,
redirect_url, salary_min, salary_max, contract_time, category.label}`, `count`.
It also has `/histogram` (salary distribution), `/top_companies` (top employers
for a search, **very useful for finding companies**), and `/categories`. Its
terms usually require attribution and may limit commercial use, which is fine
for a personal tool.

---

## 4. Company size (employee count) sources

Job feeds give **jobs, not headcount**. Options:

| Source | Cost | Canada | Notes |
|---|---|---|---|
| **Wikidata** (SPARQL `https://query.wikidata.org/sparql`) | Free, official | Good for larger and public companies | Property `P1128` = number of employees (often with a date). Small private companies are usually missing. |
| **People Data Labs** company enrichment | Free tier, small monthly allowance | Global, filterable by `location.region = ontario` | Look up each company once and store the result. |
| **Apollo.io** organization search | Free tier | Global; filter by country/region and employee range | Also useful for finding companies by size and location. |
| **Crunchbase** | Paid API (free tier limited) | Startups | – |
| **Scott's Directories** | Paid | **Canada-specific**, filterable by province and city | Strong for manufacturing and traditional industries. |
| **Canada's Top 100 Employers / Greater Toronto's Top Employers** (Mediacorp) | Free to read | Canada | Employer profiles include employee counts. Manual or semi-manual. |
| LinkedIn company About page | Free but against the terms if automated | Excellent for Canada | Size band such as "1,001–5,000 employees". Manual look-up only (see 02). |
| Estimate | Free | – | Number of open roles plus which job system they use (Ashby or Lever usually means a startup, Workday means an enterprise). |
| Manual entry in the UI | Free | – | The user fixes or enters sizes, and the app stores them. |

Suggested order: Wikidata → PDL or Apollo free tier → estimate → manual
override. Store everything; headcount changes slowly.

---

## 5. Detecting which job system a company uses

1. **From the careers page link or its HTML.** Look for these hosts:
   - `boards.greenhouse.io/{t}`, `job-boards.greenhouse.io/{t}`, `grnh.se`
     (Greenhouse short links), `boards-api.greenhouse.io`
   - `jobs.lever.co/{c}`
   - `jobs.ashbyhq.com/{b}`
   - `jobs.smartrecruiters.com/{C}`, `careers.smartrecruiters.com`
   - `apply.workable.com/{s}`
   - `{c}.recruitee.com`
   - `{c}.breezy.hr`
   - `ats.rippling.com/{c}`
   - `{c}.bamboohr.com`
   - `{t}.wd{N}.myworkdayjobs.com/{site}`
   - `{c}.jobs.personio.de`
   - Many sites embed the board in a frame or script, so search the HTML, not
     just the links.
2. **Guessing slugs from the company name.** Try the name (lowercased, with and
   without hyphens) against each feed. `research/scripts/probe.py` does this in
   parallel. **Collisions are real:** "vector", "maple", "float", "fable",
   "sonder", "rewind" matched boards that may belong to unrelated companies.
   Always confirm, for example by checking that the jobs' locations or company
   name make sense, and let the user approve the match.
3. **From aggregator results.** The apply links from Adzuna or a LinkedIn job's
   external apply link (see 02) often point straight at the job system.
4. Some companies show up on two systems (hootsuite: Greenhouse 4 and
   SmartRecruiters 8; d2l: Greenhouse 13 and Lever 5; ritual: Greenhouse 15 and
   Rippling 2; 1password: Ashby 91 and Workable 1). One is usually stale. Prefer
   the one with more recent postings.

---

## 6. Access rules and etiquette

- Official public feeds (Greenhouse, Lever, Ashby, SmartRecruiters) exist so
  jobs can be shown elsewhere; fine for personal use.
- Widget feeds (Workable, Recruitee, Breezy, Rippling): fine for personal use;
  check each one's terms.
- Undocumented endpoints (Workday, BambooHR) fall in a gray area: keep requests
  low (search per role, small pages, pauses), cache results, scan at most daily.
- Aggregators: follow each one's terms (attribution, limits).
- All requests used `User-Agent: Mozilla/5.0`. Some endpoints may reject the
  default Python user agent. Better: an honest agent string such as
  `job-radar/0.1 (personal use; contact email)`, as long as it works; test it.
- No login, no CAPTCHA solving, no LinkedIn automation.
