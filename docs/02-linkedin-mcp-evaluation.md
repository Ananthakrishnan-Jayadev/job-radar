# Evaluation of the LinkedIn MCP server

Repo: `~/Desktop/ai_projects/linkedin_mcp/linkedin-mcp-server` (clone of
`github.com/stickerdaniel/linkedin-mcp-server`, PyPI `mcp-server-linkedin`),
version **4.28.0**, at commit `a943666` on `main` (2026-10-26).

## What it is

- A Python MCP server built on **FastMCP** and **Patchright** (a patched
  Playwright). It drives a real Chromium browser signed in to the **user's own
  LinkedIn session**.
- 20 tools. **Read:** `get_person_profile`, `get_my_profile`, `search_people`,
  `get_sidebar_profiles`, `get_company_profile`, `get_company_posts`,
  `search_companies`, `get_company_employees`, `search_jobs`, `get_saved_jobs`,
  `get_job_details`, `get_job_apply_url`, `get_feed`, `search_posts`,
  `get_inbox`, `get_conversation`, `search_conversations`. **Write:**
  `send_message`, `connect_with_person`. **Other:** `close_session`.
- How it reads: it opens pages by URL and returns the page's visible text
  (`innerText`) as `{url, sections: {name: raw_text}, references?,
  section_errors?, ...}`. The AI model parses the raw text.
- It deliberately avoids LinkedIn's private "Voyager" API
  (`docs/decisions/2026-09-16-rendered-page.md`).
- About 48k lines of source and about 210k lines of tests. About 1,520 commits,
  about 1,280 of them by the maintainer (Daniel Sticker). First commit
  2025-04-12, latest 2026-10-26.

## Strengths

1. Robust against LinkedIn redesigns: visible text and URL navigation, no CSS
   class selectors, detection that works in any UI language.
2. Lower ban and legal risk than API scrapers: a real browser session, no fake
   fingerprint, no private API calls, WebRTC kept inside the proxy.
3. Very careful engineering: strict lint and type checks, a large test suite, an
   architecture doc generated from the code with checks on import direction, and
   design decisions recorded with dates.
4. Protects files and sessions: profile ownership claims, a cross-process lease
   so two servers can't overwrite each other's cookies, refusal to open a
   profile with an older browser.
5. Many ways to install: uvx, Docker (with a login viewer in the browser), a
   Claude Desktop bundle, and Codex, Claude Code and Cursor plugins.
6. Can import the LinkedIn session from 12 local Chromium-based browsers.
7. Useful errors per section, and lenient input handling (full URLs accepted,
   lists sent as strings repaired).
8. Actively maintained.

## Gaps

**Features**
- Almost no write actions: no posting, commenting, reacting, profile editing,
  invitation management, endorsements, following, or applying.
- No notifications, profile-view analytics, post analytics, groups, events,
  Sales Navigator or Recruiter. The sponsors (Cadenza, Unipile) sell these.
- Open issues: send to a thread directly (#1359), attachments (#1405),
  volunteering section (#1356), conversation history cut short (#1277), feed
  continuation (#1406, #1407), Easy Apply questions (#1341), job search offset
  resume (#1324).
- The inbox only sees conversations in the messaging sidebar.

**Output**
- No structured data: everything is raw text, which costs a lot of tokens and
  gives inconsistent results.
- Some detection relies on English-only text tables (`linkedin/text.py`,
  `*_EN_US`).

**Safety and operations**
- **Rate limits are not enforced in code.** `AGENTS.md` lists limits (10 calls a
  minute and 100 a day per tool, 1 profile page a second, 30 invitations a day,
  stop for 24 hours on a CAPTCHA), but nothing counts calls. Issue #1393 is open.
- One browser, one call at a time, one account per server (#1395).
- Stability bugs: renderer crash (#1380), Docker profile lock (#1381), unrelated
  results from job search (#1360). No stable error codes (#1389).

**Code**
- Far more infrastructure than features: `bootstrap.py` is 4,693 lines,
  `process_tree.py` 1,605, `windows_acl.py` 1,171, `daemon/` about 8k.
- Depends on one maintainer; steep learning curve.
- Automating a personal account breaks LinkedIn's User Agreement, whatever the
  technique.

## Fit for this project (job hunting, company shortlisting)

| Need | Tool | Result |
|---|---|---|
| Employee count | `get_company_profile(slug)` | The About page text includes the size band (for example "1,001–5,000 employees") and usually the number of members on LinkedIn. Raw text, which the AI must parse. |
| Active jobs | `get_company_profile(slug, sections="jobs")` | Raw text of the company's Jobs tab. **Not checked live** whether it shows a total count or just a sample. |
| Job details | `search_jobs` → `get_job_details` | Good. `search_jobs` returns `job_ids` and `total {count, exact}`. |
| Employee breakdown | `get_company_employees` | Where employees are based and which teams they're in. |
| Company search by size or industry | `search_companies` | ❌ Keywords only, one page, no filters. |
| Jobs by company | `search_jobs` | ❌ No company filter. LinkedIn's redesigned job search also drops location, job type, experience level, work type, Easy Apply and sort. Only keywords, date and paging survive. |
| Throughput | | One call at a time, roughly two pages per company. The repo's guidance is 100 calls a day per tool, so tens of companies a day at most. |

**Verdict:** useful as an optional, manual enrichment source (company size bands
for companies other sources miss), not as the core.

## What can be reused from that repo

Only concepts and small, self-contained pieces. The repo is Apache-2.0, so copied
code must keep the license notice.

1. **LinkedIn job search URL grammar**
   (`linkedin_mcp_server/linkedin/search_urls.py`). Useful only for building
   "open this search in LinkedIn" links in the UI, without automating anything:
   - `https://www.linkedin.com/jobs/search/?keywords=...&location=...`
   - date posted `f_TPR`: `past_hour=r3600`, `past_24_hours=r86400`,
     `past_week=r604800`, `past_month=r2592000`
   - experience `f_E`: internship=1, entry=2, associate=3, mid_senior=4,
     director=5, executive=6
   - job type `f_JT`: full_time=F, part_time=P, contract=C, temporary=T,
     volunteer=V, internship=I, other=O
   - work type `f_WT`: on_site=1, remote=2, hybrid=3
   - `f_EA=true` for Easy Apply; `sortBy`: date=DD, relevance=R
   - not in the builder but supported by LinkedIn: `f_C=<company id>` filters
     by company. The company's numeric id comes from `get_company_profile`'s
     `references["about"]` `{kind:"company_urn", value}`.
   - company search: `https://www.linkedin.com/search/results/companies/?keywords=...`
2. **External apply links show the company's job system.** `get_job_apply_url`
   returns the employer's apply link, for example LinkedIn's interstitial
   `/safety/go/?url=https%3A%2F%2Fgrnh.se%2F...`, which `employer_apply_url()` in
   `linkedin/job_policy.py` unwraps. The destination host (grnh.se or
   greenhouse.io, lever.co, ashbyhq.com, myworkdayjobs.com) identifies the job
   system, so a LinkedIn job can lead to the company's public feed.
   `reaches_the_public_internet()` is a careful check against links to private or
   local addresses, worth copying if we ever follow links from untrusted sources.
3. **Job states:** `ApplyType = easy_apply | external | applied | closed | unknown`.
   A useful vocabulary for our own job states.
4. **Rate-limit discipline** (`AGENTS.md`, "Live Request Limits"): a model for
   our own per-source budgets.
5. **Handling quirky MCP clients:** `_coerce_str_list` in
   `linkedin_mcp_server/tools/person.py`. Some MCP clients send a list
   parameter as a string, so accept both. Relevant if job-radar exposes an MCP
   server.
6. **MCP tool annotations:** `readOnlyHint: True, openWorldHint: True` on read
   tools; FastMCP `@mcp.tool(timeout=..., title=..., tags=...)`.
7. **Engineering practices worth copying** (pick what fits a personal tool):
   - Conventional commits: `type(scope): Subject`, imperative, under 50 chars.
   - Dated decision records (`docs/decisions/YYYY-MM-DD-*.md`).
   - Ruff for lint and format, pytest, a `tests/fixtures/` folder with recorded
     responses (we already have samples in `research/samples/`).
   - "Tests must write artifacts only to temporary directories."
   - "Verify by measurement": every endpoint claim in our docs was tested live.
8. **Using the MCP server itself, if ever:**
   `uvx mcp-server-linkedin@latest` (`--login` first, or
   `--import-from-browser auto`). Session under `~/.linkedin-mcp/`. Keep to the
   limits above, and stop for 24 hours on any CAPTCHA or restriction page.
