# Seed companies (feeds verified 2026-10-26)

Found by guessing slugs with `research/scripts/probe.py` (it tries each name
against Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Breezy,
Rippling and BambooHR in parallel) and by testing Workday site URLs by hand. The
counts are all open jobs worldwide on that day, not just Ontario ones.

**These matches are by slug only.** Before adding a company to the real seed
list, confirm that the board belongs to it, for example by checking the jobs'
locations or company name.

## Canadian companies (headquartered in Canada or with a large Canadian presence)

| Company | System | Slug or URL | Jobs | Notes |
|---|---|---|---|---|
| Wealthsimple | Ashby | `wealthsimple` | 42 | Toronto. Address shows Toronto/Ontario/Canada; salary in CA$ shown |
| Cohere | Ashby | `cohere` | 116 | Toronto AI (LLMs). **Top target for AI engineer roles** |
| KOHO | Ashby | `koho` | 9 | Toronto fintech |
| 1Password | Ashby | `1password` | 91 | Toronto. Also has a Workable board with 1 job, probably stale |
| Benevity | Ashby | `benevity` | 21 | Calgary; remote in Canada |
| Jobber | Ashby | `jobber` | 44 | Edmonton; remote in Canada |
| Neo Financial | Ashby | `neofinancial` | 58 | Calgary |
| Trulioo | Ashby | `trulioo` | 25 | Vancouver |
| Top Hat | Ashby | `top-hat` | 5 | Toronto edtech. `tophat` with no hyphen didn't match |
| Miovision | Ashby | `miovision` | 21 | Kitchener |
| Hopper | Ashby | `hopper` | 18 | Montreal |
| Clearco | Ashby | `clearco` | 5 | Toronto |
| Thinkific | Ashby | `thinkific` | 3 | Vancouver |
| Lightspeed | Ashby | `lightspeed` | 5 | Montreal (Lightspeed Commerce?). **Confirm** |
| Maple | Ashby | `maple` | 14 | Toronto telehealth? **Possible collision, confirm** |
| Float | Ashby | `float` | 21 | Toronto fintech? **Possible collision, confirm** |
| Rewind | Ashby | `rewind` | 3 | Ottawa? **Possible collision, confirm** |
| Wattpad | Lever | `wattpad` | 16 | Toronto. Salary in CAD shown (140k–180k) |
| PointClickCare | Lever | `pointclickcare` | 79 | Mississauga |
| Waabi | Lever | `waabi` | 94 | Toronto, self-driving AI. **AI target.** Also a BambooHR "Test" posting; ignore it |
| Wave | Lever | `waveapps` | 8 | Toronto |
| D2L | Greenhouse | `d2l` | 13 | Kitchener. Also Lever `d2l` with 5; check which is current |
| Shakepay | Greenhouse | `shakepay` | 10 | Montreal |
| Hootsuite | Greenhouse | `hootsuite` | 4 | Vancouver. SmartRecruiters has 8, but postings date to 2017 |
| Ritual | Greenhouse | `ritual` | 15 | Toronto. Also Rippling with 2 |
| nesto | Rippling | `nesto` | 39 (20 per page) | Montreal mortgage company. Has "Senior Applied AI Engineer", remote in Canada |
| Borrowell | Workable | `borrowell` | 2 | Toronto fintech |
| TD Bank | Workday | `https://td.wd3.myworkdayjobs.com/TD_Bank_Careers` | 1,126 | Toronto. "Data Platform Engineering Manager, Toronto-Ontario" |
| RBC | Workday | `https://rbc.wd3.myworkdayjobs.com/RBCGLOBAL1` | 820 | Toronto. "Senior Data Engineer, TORONTO-Ontario-Canada" |
| CIBC | Workday | `https://cibc.wd3.myworkdayjobs.com/search` | 201 (searched "data") | Toronto |
| BMO | Workday | `https://bmo.wd3.myworkdayjobs.com/External` | 702 | Toronto and Montreal; also many US jobs |
| Sun Life | Workday | `https://sunlife.wd3.myworkdayjobs.com/Experienced-Jobs` | 270 (searched "data") | Toronto and Waterloo. "Data Scientist" with exact date in the detail |
| Manulife | Workday | `https://manulife.wd3.myworkdayjobs.com/MFCJH_Jobs` | 454 (searched "data") | Toronto; also many Philippines jobs |
| Vector | Ashby | `vector` | 6 | **Unclear whether this is the Vector Institute (Toronto). Confirm** |
| Fable | Ashby | `fable` | 7 | Toronto accessibility company? **Possible collision** |
| Sonder | Ashby | `sonder` | 4 | **Probably not Canadian, possible collision** |

Not found on any tested feed (they use another system or a different slug):
Shopify (has its own careers site), Ada, Clio, theScore, ecobee, Coveo, League,
Questrade, Dapper Labs, Properly, Tealbook, ApplyBoard, Vidyard, Arctic Wolf,
OpenText, Kinaxis, Neo (as `neo`), Certn, Layer6 (part of TD), Mappedin, Swift
Medical, Humi, Wave (as `wave`), Dialogue, Hootsuite on other systems, Zynga,
Ubisoft, Amazon.

Found later: **Scotiabank** is on SAP SuccessFactors (`https://jobs.scotiabank.com`),
added to the seed list. Still to find: TELUS (`telus.wd3/TELUS` → 422). Others to look up: Bell, Rogers, Desjardins,
Intact, Canada Life, OMERS, Ontario Teachers', CPP Investments, Loblaw, Thomson
Reuters, CGI, Deloitte Canada, KPMG Canada, EY Canada, PwC Canada, Accenture,
IBM Canada, Ontario Power Generation, Hydro One, Metrolinx.

## Global companies with Canadian or Toronto offices (verified feeds)

| Company | System | Slug | Jobs |
|---|---|---|---|
| Faire | Greenhouse | `faire` | 72 (has a Kitchener-Waterloo office) |
| Databricks | Greenhouse | `databricks` | 895 |
| Stripe | Greenhouse | `stripe` | 720 |
| Cloudflare | Greenhouse | `cloudflare` | 454 |
| Okta | Greenhouse | `okta` | 389 |
| Affirm | Greenhouse | `affirm` | 225 |
| Lyft | Greenhouse | `lyft` | 181 |
| Pinterest | Greenhouse | `pinterest` | 163 |
| Figma | Greenhouse | `figma` | 139 |
| Instacart | Greenhouse | `instacart` | 111 |
| Dropbox | Greenhouse | `dropbox` | 23 |
| Airbnb | Greenhouse | `airbnb` | 191 |
| Snowflake | Ashby | `snowflake` | 353 |
| Canva | SmartRecruiters | `canva` | 95 |
| NVIDIA | Workday | `https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite` | 2,000 |
| Uber | SmartRecruiters | `uber` | 1 (probably not their real board) |

Whether each of these has **Ontario** roles right now is not checked. The scan will
tell.

## Names tried

`wealthsimple, cohere, shopify, faire, ada, koho, clio, wattpad, 1password, thescore,
ecobee, coveo, league, questrade, dapperlabs, sonder, benevity, jobber, hootsuite,
clearco, borrowell, nesto, properly, tealbook, ritual, figma, databricks, stripe,
instacart, pinterest, okta, affirm, lyft, uber, cloudflare, snowflake, canva, remitly,
hopper, applyboard, vidyard, arctic-wolf, arcticwolf, d2l, opentext, kinaxis, shakepay,
neo, neofinancial, trulioo, thinkific, lightspeed, dialogue, top-hat, tophat, rewind,
fable, float, certn, maple, pointclickcare, waabi, layer6, vector, vectorinstitute,
mappedin, miovision, swiftmedical, humi, wave, waveapps, dropbox, amazon, zynga, ubisoft`

Re-run with:
`python3 docs/research/scripts/probe.py name1,name2,...`
