# 2026-10-26: Where company sizes come from

The size filter was useless after phase 3: every company showed "Unknown",
because only manual entry existed. Sizes were moved to the front of phase 4.

**Precedence** (a source never overwrites a better one):
manual > stillhiring.today > Wikidata > estimate.

- **stillhiring.today** gives a current head count, but only for companies on
  its list (13 of the first 52).
- **Wikidata** is read through its regular API (`wbsearchentities`, then
  `wbgetentities` in batches of 50), not the SPARQL query service: on
  2026-10-26 SPARQL answered "429 ... rate-limiting to 1 req / min" during an
  outage. The regular API also matches aliases ("TD Bank" finds
  Toronto-Dominion Bank). Coverage is patchy: Shopify has a count (8,300 in
  2023), TD has none.
- A Wikidata match is used only when it's clear: exactly one company-type item
  (instance of business, enterprise, public company, bank...) with a head
  count, whose name matches, and in Canada for a Canadian company. Otherwise
  it's saved as a **suggestion** on the company page with a "Use this size"
  button. Searching "Hopper" returns a surname, a game and a GPU first, which
  is why this matters.
- **Estimate**, for whatever is left: from open roles worldwide and the job
  system (Workday is almost only used by large employers). Stored as the low
  end of a size band and labelled "estimated from open roles".

*Update 2026-10-27:* `enrich` now estimates first (no requests), then saves
Wikidata results every 20 companies. A failed entity request only skips its
batch. Before, everything was saved at the end, so a stopped or failed run
kept nothing and never estimated. Companies whose size came from a better
source (your own entry, stillhiring.today, your imported list) aren't looked
up, which is why the button may say 182 rather than 215.
