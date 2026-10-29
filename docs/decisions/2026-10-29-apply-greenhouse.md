# 2026-10-29: Filling in Greenhouse applications

**Asked for:** an Apply button: pick a saved résumé or upload one, click,
and see the application page already filled in.

**Scope analysis first** (in chat): no job system lets a candidate apply
through an API; every "submit application" API needs the employer's private
key. So filling in means a browser on the real form. Of 2,479 wanted open
jobs: Workday 35%, Greenhouse 21%, Ashby 12%, SuccessFactors 11%, Lever 4%.
Greenhouse first: one-page forms, the same across companies, and its public
API lists each job's questions.

**Decisions**

- **Fill, never submit.** The user reads the form, answers the rest, solves
  any CAPTCHA and presses Submit. Recruiters see every answer; CAPTCHAs are
  there to stop bots and aren't worked around.
- **Built in Job Radar**, changing the spec's non-goal "applying or filling
  in forms" to "submitting automatically". Workday stays with
  `agentic_workday`.
- **Answers are planned before the browser opens** (`apply/greenhouse.py`):
  `GET boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?questions=true`
  gives labels, field names, types and choices. Order: standard fields by
  name; the user's own `[answers]` (a piece of the question → answer);
  built-in rules (links, work authorization by country, sponsorship,
  relocation, living in Canada, "how did you hear", salary, notice). A
  choice is picked by matching ("Yes" → "Yes, I am authorized").
  Unanswerable questions are listed for the user. The `compliance` /
  demographic questions aren't even fetched into the plan.
- **Empty means ask me:** a yes/no left empty in the profile is never
  guessed (work authorization, sponsorship, relocation).
- **The form:** `job-boards.greenhouse.io/embed/job_app?for={board}&token={id}`,
  the form companies embed on their own sites, so it works when a hosted
  board is switched off; falls back to the job's own link, looking for the
  form in any frame. Fields are found by Greenhouse's id or name, else by
  their label; searchable dropdowns are typed into and the matching option
  clicked. A field that can't be filled goes on the "for you" list.
- **Submitted** = the address says "confirmation", or a thank-you message
  shows *and* the form is gone (a thank-you line beside the form doesn't
  count). Then the job is marked Applied (a later stage isn't moved back)
  and a note records the date and résumé. Closing the window changes
  nothing.
- **Browser:** Playwright's Firefox (the user only uses Firefox), headed.
  Its download goes in `.venv/ms-playwright`, not `~/.cache`, to keep the
  rule that nothing installs outside the venv.
- **Personal data:** `profile.local.toml` is git-ignored (the repository is
  public); résumés live in `data/resumes/`, also git-ignored. Nothing about
  the user is sent anywhere except the form they submit.
- One application window at a time (`web/applier.py`), followed by the
  job page's Apply panel.

**After the first real try (2026-10-29):**

- *The résumé didn't attach.* Files now go only on an `input[type=file]`
  (an element sharing the id "resume" could catch it before), and the form
  must then show the file's name. If it doesn't, the form's own Attach
  button is clicked and the file handed to the file chooser, as a person
  would. If that fails too, the résumé goes on the "for you" list with the
  reason.
- *A country dropdown before the phone number* ("Canada +1"): not in the
  API's questions, so it's set from the profile's `country`, unless the job
  asks a "Country" question of its own.
- *Current company and job title*: new `current_company` / `current_title`
  in the profile's `[work]` (also "most recent employer"). Left empty, they
  stay on the "for you" list.
- Every field that can't be filled now says why in the panel, to make the
  next fix quick.

**Still unverified:** the embed address on
today's Greenhouse, its field ids, the searchable dropdowns and the
thank-you detection. Tests use a stand-in page; the user's first application
is the real check.

**Later:** Ashby and Lever; drafting answers to a job's own questions from
the résumé with a local model; a Workday hand-off.
