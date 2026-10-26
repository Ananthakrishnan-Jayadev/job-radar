# 2026-10-26: Choices made while building scanning (phase 2)

1. **Workday search terms live in config until saved searches exist.**
   Boards with more than `workday.max_list` (400) Canadian jobs are searched
   per term. Until the web UI can mark saved searches "use for sources"
   (phase 3), the terms come from `workday.search_terms` in `config.toml`.
   Saved searches, once present, replace the config list.

2. **Partial reads never close jobs.** A connector reports `complete = False`
   when it read only part of a board: Workday in search mode or over its
   list limit, and Rippling when its page parameter doesn't work. The scanner
   then stores what it saw but closes nothing.

3. **Closing uses the exact set of jobs seen,** not timestamps. Comparing
   `last_seen` to the scan time failed when two scans ran within one second.

4. **Workday list entries don't overwrite detail data.** A job whose detail
   page was already fetched keeps its full locations and description when a
   later scan only reads the list (`RawJob.details_fetched = False`).

5. **Descriptions are only stored where the list gives them:** Greenhouse,
   Lever, Ashby, Recruitee, and Workday (from the detail page). SmartRecruiters,
   Workable, Breezy, Rippling and BambooHR lists have none; fetching one page
   per job would multiply requests. Keyword search still covers their titles,
   company and department.

6. **Unconfirmed boards are scanned.** Their jobs are only stored if they're
   in Canada, which already filters most slug collisions. The web UI (phase 3)
   will show them as unconfirmed so they can be confirmed or disabled.

7. **User agent.** Requests send `job-radar/0.1 (personal use; <contact>)`.
   If a host answers 403, that host gets one retry with the browser-like
   `http.fallback_user_agent`, and keeps using it for the rest of the scan.

8. **Rippling's page parameter is still unverified** (`?page=N` assumed, pages
   counted from 0). If a page repeats the previous one, the connector stops,
   warns, and marks the read partial. The first live scan settles it.
