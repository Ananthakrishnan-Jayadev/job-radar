# 2026-10-28: Experience level of each job

**Question:** can the level (intern to lead) be read from each job
deterministically, or does it need an AI model?

**Measured on the real database:** of 2,335 open jobs matching `roles.toml`,
a level word in the title or a stated number of years in the description
covers about 90%. That leaves 221 the rules can't place.

**Decision: rules first, a model only for the leftovers, only on request.**

- **Rules** (`jobradar/levels.py`): the title wins (Intern / Co-op, Staff /
  Principal / Lead / Manager / Director, Senior, Intermediate, Junior / New
  Grad / Associate, "Engineer II" grades); otherwise the years the description
  asks for (0–1 entry, 2–4 mid, 5–7 senior, 8+ lead). English and French
  patterns; numbers over 15, or after "for / over / since..." are company
  history and ignored.
- **Largest number, not smallest** (changed the same day): the first version
  took the smallest so no job would be hidden, but once "N+ years building…"
  lines counted too, a Director post with "10+ years in software with 5+
  years in leadership" read as 5, and others dropped to a single skill's 2 or
  3. The headline requirement is the largest; a range counts from its start.
- **Years filter:** under 3 (0–2), 3–5, more than 5 (6+), not stated, as the
  user asked; stated numbers only.
- **The model must pick a level** (no "unknown" in its choices), since the
  user prefers a best guess to a blank; it gives years only when stated.
  First test on 20 jobs: Gemma placed 11, Nemotron 9 while it could still say
  "unknown"; they agreed on the rest.
- **Only wanted jobs** (roles.toml): the user browses with the role filter on,
  and it keeps the model's work to ~200 jobs once, then a few per scan.
- **Ollama, not a paid API:** the user has free cloud access through Ollama
  (`gemma4:31b-cloud`, `nemotron-3-nano:30b-cloud`). Called on
  `localhost:11434/api/chat` with httpx (no new dependency), a JSON schema in
  `format`, temperature 0, the first 6,000 characters of the description.
  One job at a time, each answer saved at once; a job the model can't place
  either isn't asked again. Never part of a scan.
- **Stored:** `experience_level`, `min_years`, `level_source` ("title",
  "years", "none", "ollama:<model>"). A changed title or description clears
  them (trigger) so they're worked out again. Bumping `RULES_VERSION` redoes
  rule-made levels but keeps the model's.

**Known weak spots:** "Associate" means mid-level at banks; "Lead" can be a
role name ("Lead Generation"); the largest-years choice can overstate a job
that wants "5 years with a degree, or 3 with a master's". The title still
wins in all of those, which covers most.

**Model choice:** compare both with `jobradar levels --ai --dry-run --limit 50
--model ...` and set the better one in `config.toml`.
