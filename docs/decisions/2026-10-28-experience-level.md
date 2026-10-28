# 2026-10-28: Experience level of each job

**Question:** can the level (intern to lead) be read from each job
deterministically, or does it need an AI model?

**Measured on the real database:** of 2,335 open jobs matching `roles.toml`,
a level word in the title or a stated number of years in the description
covers about 90%. That leaves 221 the rules can't place.

**Decision: rules first, a model only for the leftovers, only on request.**

- **Rules** (`jobradar/levels.py`): the title wins (Intern / Co-op, Staff /
  Principal / Lead / Manager / Director, Senior, Intermediate, Junior / New
  Grad / Associate, "Engineer II" grades); otherwise the smallest number of
  years the description asks for (0–1 entry, 2–4 mid, 5–7 senior, 8+ lead).
  The smallest, so a job you might qualify for isn't hidden. English and
  French patterns; numbers over 15 ignored (company history).
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
role name ("Lead Generation"); the smallest-years choice can understate a
senior job that also names a minor skill with fewer years. The title still
wins in all of those, which covers most.

**Model choice:** compare both with `jobradar levels --ai --dry-run --limit 50
--model ...` and set the better one in `config.toml`.
