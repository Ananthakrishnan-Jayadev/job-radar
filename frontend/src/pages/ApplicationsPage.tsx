import NumberFlow from "@number-flow/react";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import AddJobByLink from "../components/AddJobByLink";
import BarChart from "../components/BarChart";
import StatusSelect from "../components/StatusSelect";
import { JOB_STATUS_LABEL, LEVEL_LABEL, formatDate, formatDateTime, plural } from "../format";
import { useApp, useLoad } from "../state";
import type { Applications, JobStatus, TrackedJob } from "../types";

// The stages in the order an application moves through them.
const STAGES: Exclude<JobStatus, "new" | "not_interested">[] = ["saved", "applied", "interviewing", "offer", "rejected"];

/** Jobs list filtered to one status; closed postings included, since tracking outlives them. */
const jobsWith = (status: string) => `/?status=${status}&include_closed=1`;

export default function ApplicationsPage() {
  const { dataVersion } = useApp();
  const data = useLoad(() => api.applications(), String(dataVersion));
  const d = data.data;
  const [adding, setAdding] = useState(false);

  return (
    <div className="applications-page">
      <div className="results-head">
        <h1>Applications</h1>
        {!adding && (
          <button type="button" onClick={() => setAdding(true)}>
            <Plus size={15} aria-hidden="true" />
            Add a job by link
          </button>
        )}
      </div>
      {adding && <AddJobByLink onClose={() => setAdding(false)} />}
      {data.error && (
        <p className="error" role="alert">
          {data.error}
        </p>
      )}
      {!d && data.loading && <p className="loading">Loading…</p>}
      {d && (
        <>
          <Pipeline d={d} />
          {Object.values(d.counts).every((n) => n === 0) ? (
            <div className="empty">
              <p>
                Nothing tracked yet. Set a job's status to Saved or Applied on the <Link to="/">Jobs</Link> page, or add
                one you found elsewhere with "Add a job by link", and it shows up here.
              </p>
            </div>
          ) : (
            <div className="app-grid">
              <WeekChart weeks={d.per_week} />
              <FollowUps d={d} />
              <TrackedTable
                title="In progress"
                empty="No applications in progress."
                jobs={d.active}
                onChange={data.reload}
                dateLabel="Applied"
              />
              <TrackedTable
                title="Saved, not applied yet"
                empty="No saved jobs waiting."
                jobs={d.saved}
                onChange={data.reload}
                dateLabel="Saved"
              />
              <Recent d={d} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Pipeline({ d }: { d: Applications }) {
  const rate = d.applied_total ? Math.round((100 * d.heard_back) / d.applied_total) : 0;
  return (
    <section aria-label="Where your applications stand">
      <ol className="pipeline">
        {STAGES.map((s) => (
          <li key={s}>
            <Link to={jobsWith(s)} className={`stage status-${s}`}>
              <span className="count">
                <NumberFlow value={d.counts[s]} />
              </span>
              <span className="label">{JOB_STATUS_LABEL[s]}</span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="pipeline-summary">
        You've applied to {plural(d.applied_total, "job")}.{" "}
        {d.applied_total > 0 && (
          <>
            {d.heard_back} heard back ({rate}%), {plural(d.interviews, "interview")}.{" "}
          </>
        )}
        {d.counts.not_interested > 0 && (
          <Link to={jobsWith("not_interested")}>{d.counts.not_interested} marked not interested.</Link>
        )}
      </p>
    </section>
  );
}

/** Applications per week, by the date you applied. */
function WeekChart({ weeks }: { weeks: Applications["per_week"] }) {
  const last = weeks.length - 1;
  const thisWeek = weeks[last]?.applied ?? 0;
  const bars = weeks.map((w, i) => ({
    key: w.week,
    value: w.applied,
    label: i === last ? "This week" : i % 3 === 2 ? formatDate(w.week) : "",
    tip: `${i === last ? "This week" : `Week of ${formatDate(w.week)}`}: ${plural(w.applied, "application")}`,
  }));
  return (
    <section className="panel week-chart">
      <h2>Applications per week</h2>
      <p className="hint">
        Last 12 weeks, by the date you applied. {plural(thisWeek, "application")} this week.
      </p>
      <BarChart bars={bars} />
    </section>
  );
}

function FollowUps({ d }: { d: Applications }) {
  return (
    <section className="panel follow-up">
      <h2>Time to follow up</h2>
      <p className="hint">No news for {d.follow_up_days} days or more.</p>
      {d.follow_up.length === 0 ? (
        <p className="quiet">Nothing waiting that long.</p>
      ) : (
        <ul className="follow-list">
          {d.follow_up.map((j) => (
            <li key={j.id}>
              <Link to={`/jobs/${j.id}`}>{j.title}</Link>
              <span className="muted">
                {j.company}, {JOB_STATUS_LABEL[j.status].toLowerCase()}
              </span>
              <span className="days">{j.days_since_change} days</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TrackedTable(props: {
  title: string;
  empty: string;
  jobs: TrackedJob[];
  onChange: () => void;
  dateLabel: string;
}) {
  const { title, empty, jobs, onChange, dateLabel } = props;
  const saved = dateLabel === "Saved";
  return (
    <section className="panel tracked">
      <h2>
        {title} <span className="muted">{jobs.length}</span>
      </h2>
      {jobs.length === 0 ? (
        <p className="quiet">{empty}</p>
      ) : (
        <div className="table-wrap">
          <table className="jobs">
            <thead>
              <tr>
                <th scope="col">Job</th>
                <th scope="col">Level</th>
                <th scope="col">{dateLabel}</th>
                <th scope="col">Last change</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className={j.closed_at ? "is-closed" : ""}>
                  <td className="job-cell">
                    <Link to={`/jobs/${j.id}`} className="job-title">
                      {j.title}
                    </Link>
                    <span className="job-company">
                      <Link to={`/companies/${j.company_id}`}>{j.company}</Link>
                      {j.closed_at && (
                        <span className={`tag${saved ? " warn" : ""}`} title={`Gone from the board ${formatDate(j.closed_at)}`}>
                          Posting closed
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="nowrap">{j.level ? LEVEL_LABEL[j.level] : <span className="muted">–</span>}</td>
                  <td className="nowrap num">{formatDate(saved ? j.status_changed_at : j.applied_at)}</td>
                  <td className="nowrap num">{daysAgo(j.days_since_change)}</td>
                  <td>
                    <StatusSelect jobId={j.id} status={j.status} onChange={onChange} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Recent({ d }: { d: Applications }) {
  if (d.recent.length === 0) return null;
  return (
    <section className="panel recent-changes">
      <h2>Recent changes</h2>
      <ul className="history">
        {d.recent.map((e) => (
          <li key={`${e.id}-${e.at}`}>
            <span>
              <Link to={`/jobs/${e.id}`}>{e.title}</Link> <span className="muted">at {e.company}</span>:{" "}
              {e.old ? JOB_STATUS_LABEL[e.old as JobStatus] : "—"} to{" "}
              <span className={`dot-label status-${e.new}`}>{e.new ? JOB_STATUS_LABEL[e.new as JobStatus] : "—"}</span>
            </span>
            <time dateTime={e.at}>{formatDateTime(e.at)}</time>
          </li>
        ))}
      </ul>
    </section>
  );
}

function daysAgo(days: number | null): string {
  if (days === null) return "—";
  if (days === 0) return "Today";
  return days === 1 ? "Yesterday" : `${days} days ago`;
}
