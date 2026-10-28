# 2026-10-28: Experience level and years asked

**Question:** can the level (intern to lead) and the years of experience a
job needs be read from each posting deterministically, or does it need an AI
model?

**Measured on the real database:** of about 2,480 open jobs matching
`roles.toml`, the rules give a level to all but about 200 (a level word in
the title, or a stated number of years), and find the years in about 1,800.
About 680 state no years the rules can read.

**Decision: rules first, a model only for what they miss, only on request.**

## Rules (`jobradar/levels.py`)

- **Level from the title first:** Intern / Co-op / Student → intern; Staff /
  Principal / Lead / Manager / Director / Head of / VP → lead; Senior / Sr →
  senior; Intermediate → mid; Junior / New Grad / Associate → entry;
  "Engineer II" style grades (I entry, II mid, III/IV senior).
- **Years from the description, for every wanted job** (not derived from the
  level): "5+ years of experience", "5+ years building…", "at least 3 years
  in…", "3 years required", "2+ années d'expérience", "(5 ans minimum)".
- **The largest number counts.** The first version took the smallest so no
  job would be hidden, but once "N+ years building…" lines counted, a Director
  post with "10+ years in software with 5+ years in leadership" read as 5,
  and others dropped to one skill's 2 or 3. The headline requirement is the
  largest. A range counts from its start ("7-10+ years" is 7).
- **Skipped:** numbers over 15, and numbers right after "for / over / past /
  since / trusted / serving" ("trusted for 10+ years" is the company's). Only
  words directly before the number count, so "what we're looking for:
  - 5+ years" is still read.
- **Level from the years** when the title has none: 0–1 entry, 2–4 mid, 5–7
  senior, 8+ lead.
- **Only wanted jobs** (roles.toml): the user browses with the role filter on.

## Filters

- **Experience:** intern, entry, mid, senior, lead+, unknown.
- **Years of experience asked:** under 3 (0–2), 3–5, more than 5 (6+), not
  stated, as the user asked. Stated numbers only, so "5+ years" is in 3–5.

## The model (optional)

- **Ollama, not a paid API:** the user has free cloud access through Ollama
  (`gemma4:31b-cloud`, `nemotron-3-nano:30b-cloud`) after `ollama signin`; no
  API key, since the app calls the local server
  (`localhost:11434/api/chat`) with httpx (no new dependency). Temperature 0,
  the first 6,000 characters of the description.
- **Which jobs:** open wanted jobs with a description that lack a level or
  years (about 600 at first, then a few per scan). Only empty fields are
  filled: a title's level stays. Each job is read once (`level_asked`); a
  changed title or description is read again. Never part of a scan.
- **Always a level, years only when stated.** The user prefers a best guess
  to a blank, so "unknown" isn't one of its choices; inventing a number of
  years would make the years filter lie, so it may answer null there.
- **Answers in two forms.** Cloud models ignore the JSON schema in `format`
  and reply "level: senior / min_years: null", so both that and JSON are read
  (the first test counted every answer as unusable).
- **Model choice:** on 20 jobs (while "unknown" was still allowed) Gemma
  placed 11, Nemotron 9, and they agreed on the rest. Gemma is the default in
  `config.toml`. `jobradar levels --ai --dry-run --limit N --model ...`
  compares models without saving.
- One request at a time, each answer saved at once; a usage limit or a
  stopped run keeps what was saved.

## Stored (schema 6 and 7)

`experience_level`, `min_years`, `level_source` ("title", "years", "none",
"ollama:<model>"), `level_asked` (the model that read the job). A changed
title or description clears all four (trigger). Bumping `RULES_VERSION`
redoes the rule-made rows but keeps the model's levels.

## Known weak spots

"Associate" means mid-level at banks; "Lead" can be part of a role name
("Lead Generation"); the largest-years choice can overstate a job that wants
"5 years with a degree, or 3 with a master's". Many postings state no years
at all (what's left mentions only perks like "4 weeks per year" or company
history), so "not stated" won't reach zero.
