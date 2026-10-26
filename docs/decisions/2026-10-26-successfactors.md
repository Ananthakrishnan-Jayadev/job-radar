# 2026-10-26: SAP SuccessFactors as the 11th job system (Scotiabank)

Scotiabank's careers site (`jobs.scotiabank.com`) isn't on Workday, which is
why `scotiabank.wd3/External` answered 422. It's a SAP SuccessFactors "Career
Site Builder" site: assets from `rmkcdn.successfactors.com` and a `j2w.init`
script.

Ways to read it, checked on 2026-10-26:

- **Search pages** (`/search/?q=&locationsearch=ontario`): HTML, 25 per page,
  682 Ontario results, so about 28 page requests for Ontario alone. Has dates.
- **Keyword RSS** (`/services/rss/job/?keywords=(ontario)`): only 20 items,
  and the keyword matches description text (first hit was in Vernon, BC).
  Not usable.
- **`/sitemap.xml`**: despite its name, an RSS feed of **every** open job with
  Google job fields (`g:id`, `g:location` "Toronto, ON, CA", `g:job_function`,
  full description). One request; 1,471 jobs, 1,060 in Canada, 682 in Ontario
  (the same 682 the search page shows). **Chosen.**

Costs of the choice: the feed is 38 MB, almost all of it base64 images inside
descriptions (they are stripped before parsing; parsing takes about 2 seconds).
There is no posting date, only an expiry date, so a job's date is the day the
scan first saw it.

The board is the site's address (`https://jobs.scotiabank.com`). Detection
recognizes such sites from a careers page by the two markers above. Other
large employers use SuccessFactors too, so this isn't Scotiabank-only.
