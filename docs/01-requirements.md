# Requirements

## What the user said, in order

1. *"this folder is an open sourced linkedin mcp that i cloned from git, but i dont
   think it is good enough, first do a full understanding and give me the pros and
   where is project lacks"*: led to the evaluation in `02-linkedin-mcp-evaluation.md`.
2. *"i need it for job hunting, to shortlist companies based on employee count and
   active job listings. Will it be useful?"*: the **two original criteria** are
   **employee count** and **active job listings**.
3. *"how does [Composio] provide linkedin mcp access if linkedin makes it forbidden
   for everyone else"*: answered in `03-data-sources.md` (official OAuth API, very
   narrow, no job or company data).
4. *"im looking for opportunities filtered down to canada and ontario, i couldnt find
   a website that have canada info that much, most of the sites are US companies
   heavy"*: led to `04-canadian-sources.md`.
5. *"does greenhouse, bamboohr and workday have apis? with some free access at
   least?"*: tested; see `03-data-sources.md`.
6. *"check if there is anything else useful for canada"*: seven more sources
   tested, plus job-search aggregators.
7. *"im planning to build a whole new application since linkedin have such risk
   using free api companies"*: the decision to build our own tool.
8. *"personal tool - idea is to do job hunting not applying (at least for now) -
   need to scour through these apis and find out companies that have job postings
   that i need (ai engineer, data analyst etc), then i can manually box them in -
   mark them as applied or not to track them, and some other features to make the
   experience better"*: **the core requirement** (below).
9. *"dont start building, we will do it in a separate folder with proper plan,
   tasks, phasing and all"*: process requirement. Plan first.

## Functional requirements (agreed)

**Discovery**
- Search many public company job feeds and job-search APIs for postings that
  match the user's **target roles**: AI engineer and data analyst explicitly,
  data scientist, ML engineer and similar implied by "etc.". Role matching must
  be configurable.
- Filter to **Canada and Ontario**: Ontario jobs plus Canada-wide remote roles,
  with a wider "all of Canada" option.
- Surface **companies** that have matching postings, not only individual jobs.
- Show **company size (employee count)** and **number of active postings** per
  company. These were the original shortlisting criteria.

**Tracking ("box them in")**
- The user manually marks jobs and companies: applied / not applied, and
  probably richer statuses (saved, applied, interviewing, rejected, not
  interested).
- Tracking must survive the posting disappearing from the source. A job that
  closes after you applied must stay visible, marked as closed.

**"Some other features to make the experience better"** (the user left this
open; ideas proposed so far, none confirmed):
- "New since last visit" markers, from the first time a job was seen.
- Filters: role, location (Ontario, Canada remote, Canada), company, status,
  text search, posted within N days.
- Per company: Ontario matching roles vs total roles, size, which job system it
  uses, notes.
- Hiring momentum: change in a company's open roles over time, from daily
  snapshots.
- Salary, where the source gives it (Lever, Ashby and Recruitee do).
- Export to CSV.
- Notes per job and per company, and the date applied.
- Duplicate handling: the same job from a company feed and from an aggregator.
- Later, optionally: expose the data as an MCP server so Claude can query the
  shortlist, and hand a Workday job to `agentic_workday` for applying.

## Non-functional requirements

- **Personal use, one user, runs locally.** No auth, no hosting concerns.
- **Low legal and account risk.** Prefer official public APIs, use undocumented
  endpoints gently, use no LinkedIn automation in the core.
- **Gentle on sources:** scheduled scans (for example daily), caching, small
  page sizes, pauses between requests.
- **Resilient:** one source breaking must not break the others (isolated
  connectors).

## Explicitly out of scope (for now)

- Applying to jobs or filling in forms.
- Multi-user use, SaaS, deployment.
- LinkedIn scraping as a data source in the core.
