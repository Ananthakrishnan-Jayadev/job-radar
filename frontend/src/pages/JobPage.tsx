import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import StatusSelect from "../components/StatusSelect";
import {
  JOB_STATUS_LABEL,
  LEVEL_LABEL,
  SIZE_LABEL,
  SYSTEM_LABEL,
  WORKPLACE_LABEL,
  formatDate,
  formatDateTime,
  levelSourceText,
} from "../format";
import { useLoad } from "../state";
import type { JobDetail, JobStatus } from "../types";

export default function JobPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const job = useLoad(() => api.job(id), String(id));

  if (job.error) return <p className="error" role="alert">{job.error}</p>;
  if (!job.data) return <p className="loading">Loading…</p>;
  const j = job.data;
  const update = (change: Partial<JobDetail>) => job.setData((d) => (d ? { ...d, ...change } : d));

  return (
    <article className="job-page">
      <button type="button" className="link back" onClick={() => navigate(-1)}>
        Back to results
      </button>

      <header className="job-head">
        <h1>{j.title}</h1>
        <p className="job-sub">
          <Link to={`/companies/${j.company_id}`}>{j.company}</Link>
          <span>{SIZE_LABEL[j.size_band] ?? j.size_band} employees</span>
        </p>
        {j.closed_at && (
          <p className="notice">This posting disappeared from {j.company}'s job board on {formatDate(j.closed_at)}.</p>
        )}
        {!j.board_confirmed && (
          <p className="notice">
            This job comes from a board matched by name only. Check it belongs to {j.company} on the company page.
          </p>
        )}
      </header>

      <div className="job-columns">
        <div className="job-main">
          <dl className="facts">
            <dt>Where</dt>
            <dd>
              {j.locations.filter((l) => l.in_canada).map((l) => l.label).join("; ") || j.location}
              {j.locations.some((l) => !l.in_canada && (l.city || l.country)) && (
                <span className="hint"> Also listed outside Canada.</span>
              )}
            </dd>
            <dt>Level</dt>
            <dd>
              {j.level ? LEVEL_LABEL[j.level] : "Not clear"}
              {j.min_years !== null && <>, asks for {j.min_years}+ years</>}
              {j.level && levelSourceText(j.level_source) && (
                <span className="hint"> ({levelSourceText(j.level_source)})</span>
              )}
            </dd>
            <dt>Workplace</dt>
            <dd>{WORKPLACE_LABEL[j.workplace]}</dd>
            <dt>Posted</dt>
            <dd>{formatDate(j.posted_at)}</dd>
            <dt>First found</dt>
            <dd>{formatDate(j.first_seen)}</dd>
            {j.salary && (
              <>
                <dt>Salary</dt>
                <dd>{j.salary}</dd>
              </>
            )}
            {j.employment_type && (
              <>
                <dt>Type</dt>
                <dd>{j.employment_type}</dd>
              </>
            )}
            {j.department && (
              <>
                <dt>Team</dt>
                <dd>{j.department}</dd>
              </>
            )}
            <dt>Source</dt>
            <dd>{SYSTEM_LABEL[j.system] ?? j.system}</dd>
          </dl>

          <h2>Description</h2>
          {j.description ? (
            <div className="description">{j.description}</div>
          ) : (
            <p className="hint">
              {j.system === "workday"
                ? "The full description is fetched on a later scan. Open the posting to read it now."
                : "This job board doesn't include descriptions. Open the posting to read it."}
            </p>
          )}
        </div>

        <aside className="job-side">
          <section className="panel">
            <h2>My tracking</h2>
            <label className="stack">
              Status
              <StatusSelect
                jobId={j.id}
                status={j.status}
                onChange={(t) => {
                  update({ status: t.status, applied_at: t.applied_at });
                  job.reload();
                }}
              />
            </label>
            <AppliedDate job={j} onSaved={(applied_at) => update({ applied_at })} />
            <Notes job={j} onSaved={(notes) => update({ notes })} />
          </section>

          <section className="panel links">
            <h2>Links</h2>
            <a href={j.links.job} target="_blank" rel="noreferrer">
              Open the posting
            </a>
            {j.links.careers && (
              <a href={j.links.careers} target="_blank" rel="noreferrer">
                {j.company} careers page
              </a>
            )}
            <a href={j.links.linkedin} target="_blank" rel="noreferrer">
              Search this job on LinkedIn
            </a>
          </section>

          {j.events.length > 0 && (
            <section className="panel">
              <h2>History</h2>
              <ol className="history">
                {j.events.map((e, i) => (
                  <li key={i}>
                    <span>{JOB_STATUS_LABEL[e.new as JobStatus] ?? e.new}</span>
                    <time dateTime={e.at}>{formatDateTime(e.at)}</time>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </aside>
      </div>
    </article>
  );
}

function AppliedDate({ job, onSaved }: { job: JobDetail; onSaved: (value: string | null) => void }) {
  const [value, setValue] = useState(job.applied_at ?? "");
  useEffect(() => setValue(job.applied_at ?? ""), [job.applied_at]);
  if (!job.applied_at && !["applied", "interviewing", "offer", "rejected"].includes(job.status)) return null;

  async function save(next: string) {
    setValue(next);
    const result = await api.patchJob(job.id, { applied_at: next || null });
    onSaved(result.applied_at);
  }

  return (
    <label className="stack">
      Applied on
      <input type="date" value={value} onChange={(e) => save(e.target.value)} />
    </label>
  );
}

function Notes({ job, onSaved }: { job: JobDetail; onSaved: (notes: string) => void }) {
  const [text, setText] = useState(job.notes);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  useEffect(() => setText(job.notes), [job.notes]);
  const changed = text !== job.notes;

  async function save() {
    setState("saving");
    const result = await api.patchJob(job.id, { notes: text });
    onSaved(result.notes);
    setState("saved");
  }

  return (
    <div className="stack">
      <label htmlFor="notes">Notes</label>
      <textarea
        id="notes"
        rows={5}
        value={text}
        placeholder="Referral, recruiter name, what to mention…"
        onChange={(e) => {
          setText(e.target.value);
          setState("idle");
        }}
      />
      <div className="row">
        <button type="button" className="primary" disabled={!changed || state === "saving"} onClick={save}>
          Save notes
        </button>
        {state === "saved" && !changed && <span className="hint">Notes saved.</span>}
      </div>
    </div>
  );
}
