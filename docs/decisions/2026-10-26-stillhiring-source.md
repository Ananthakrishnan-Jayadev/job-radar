# 2026-10-26: stillhiring.today as a company source

The user wants https://stillhiring.today/ (a community-sourced list of tech
companies that are hiring) fed into job-radar, kept current automatically.

## What it is (checked 2026-10-26)

- The site embeds a shared Airtable view (`airtable.com/embed/shrI8dno1rMGKZM8y`).
  There is no official API for it (Airtable's API needs the owner's key) and
  no published terms of use.
- The embed page carries a short-lived signed `accessPolicy` and the URL
  `/v0.3/view/{viewId}/readSharedViewData?...`; the browser calls it with the
  headers `x-airtable-application-id`, `x-requested-with: XMLHttpRequest`,
  `x-time-zone`, `x-user-locale`. The response is
  `{msg, data: {table: {columns, rows}}}`; select options are ids resolved
  through `columns[].typeOptions.choices`.
- **Undocumented and against the spirit of Airtable's terms.** The user
  accepted this (same gray area as Workday/BambooHR). Use it gently: two
  requests per refresh, at most once a day, and expect it to break.

## The data (1,129 companies on 2026-10-26)

Columns: Company Name, Jobs Page (button: `{label, url}`), Employees (number),
HQ Country (ISO, e.g. `CA`), HQ State (`CA-ON`), HQ City, Tagline, Open Roles
Found by Function, Engineering/Product/Design Open Roles Found, Keyplay Growth
Signals, Funding, Remote Hiring? (a lookup).

- HQ country: US 890, **CA 79**, GB 44, NL 15, DE 12, others.
- Jobs Page hosts: company site 721, Greenhouse 125, Ashby 90, Lever 77,
  Workday 72, Rippling 13, Breezy 11, Recruitee 8, BambooHR 7,
  SmartRecruiters 5. Some point at LinkedIn company pages (useless for us);
  some at systems we don't support yet: Gem (`jobs.gem.com`), Teamtailor,
  JazzHR (`applytojob.com`).

## How it fits (phase 4)

- A **company source** (not a job source): refresh pulls the table, keeps
  rows with HQ Country = CA by default, and lists them on the Candidates page
  as new / still listed / no longer listed.
- Non-Canadian-HQ companies whose Jobs Page is a supported job system can be
  offered as an opt-in ("check for Canadian roles"): US companies with
  Toronto offices (Affirm, Lyft, Okta...) are a big share of our jobs.
- **Employees** fills `employee_count` with `size_source = 'stillhiring'`
  (below manual, above estimate).
- **Jobs Page** feeds job-system detection; a direct ATS link becomes a board
  with no guessing.
- Nothing is added to scanning without the user approving it.
