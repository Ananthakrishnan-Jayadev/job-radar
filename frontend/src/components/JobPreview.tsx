// The right half of the split view: the selected posting, with the decision
// buttons at the top so you can read and decide without leaving the list.

import { ExternalLink, Maximize2 } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { LEVEL_LABEL, SIZE_LABEL, SYSTEM_LABEL, WORKPLACE_LABEL, formatDate, groupPlaces, levelSourceText, tidyText } from "../format";
import { Highlight } from "../highlight";
import { useLoad } from "../state";
import type { JobStatus, JobSummary } from "../types";
import DecisionBar from "./DecisionBar";
import StatusSelect from "./StatusSelect";

interface Props {
  job: JobSummary;
  /** The search's words, marked in the title and description. */
  pattern: RegExp | null;
  busy: boolean;
  onDecide: (status: JobStatus) => void;
}

export default function JobPreview({ job, pattern, busy, onDecide }: Props) {
  const detail = useLoad(() => api.job(job.id), String(job.id));
  const d = detail.data?.id === job.id ? detail.data : undefined;
  const places = d ? d.locations.filter((l) => l.in_canada).map((l) => l.label).join("; ") || d.location : job.location;

  return (
    <motion.article
      key={job.id}
      className="preview"
      aria-label={`Selected job: ${job.title}`}
      initial={{ opacity: 0.35, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
    >
      <header className="preview-head">
        <h2>
          <Link to={`/jobs/${job.id}`}>
            <Highlight text={job.title} pattern={pattern} />
          </Link>
        </h2>
        <p className="job-sub">
          <Link to={`/companies/${job.company_id}`}>{job.company}</Link>
          <span>{SIZE_LABEL[job.size_band] ?? job.size_band} employees</span>
        </p>
      </header>

      <div className="preview-decide">
        <DecisionBar status={job.status} busy={busy} showKeys onDecide={onDecide} />
        <div className="preview-more">
          <StatusSelect jobId={job.id} status={job.status} onPick={onDecide} />
          <Link to={`/jobs/${job.id}`} className="button quiet" title="Open the full page (O)">
            <Maximize2 size={14} aria-hidden="true" />
            Full page
          </Link>
          <a className="button quiet" href={d?.links.job ?? job.url} target="_blank" rel="noreferrer">
            <ExternalLink size={14} aria-hidden="true" />
            Posting
          </a>
        </div>
        <p className="keys" aria-hidden="true">
          <span>
            <kbd>J</kbd>
            <kbd>K</kbd> next and previous job
          </span>
          <span>
            <kbd>U</kbd> undo
          </span>
          <span>
            <kbd>/</kbd> search
          </span>
          <span>
            <kbd>?</kbd> all keys
          </span>
        </p>
      </div>

      <dl className="facts">
        <div className={job.group ? "facts-wide" : undefined}>
          <dt>{job.group ? `Where (posted ${job.group.length} times)` : "Where"}</dt>
          <dd>
            {job.group ? (
              <ul className="group-places">
                {groupPlaces(job.group).map(({ location, ids }) => (
                  <li key={location}>
                    {ids.includes(job.id) ? (
                      <span aria-current="true">{location}</span>
                    ) : (
                      <Link to={`/jobs/${ids[0]}`} title="This place's own posting">
                        {location}
                      </Link>
                    )}
                    {ids.length > 1 && <span className="muted"> ×{ids.length}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              places
            )}
          </dd>
        </div>
        <div>
          <dt>Level</dt>
          <dd>
            {job.level ? LEVEL_LABEL[job.level] : "Not stated"}
            {job.min_years !== null && <>, asks for {job.min_years}+ years</>}
            {job.level && levelSourceText(job.level_source) && (
              <span className="hint"> ({levelSourceText(job.level_source)})</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Workplace</dt>
          <dd>{WORKPLACE_LABEL[job.workplace]}</dd>
        </div>
        <div>
          <dt>Posted</dt>
          <dd>{job.posted_at ? formatDate(job.posted_at) : <span className="muted">Not given</span>}</dd>
        </div>
        <div>
          <dt>Found</dt>
          <dd>{formatDate(job.first_seen)}</dd>
        </div>
        {job.salary && (
          <div>
            <dt>Salary</dt>
            <dd>{job.salary}</dd>
          </div>
        )}
        <div>
          <dt>Source</dt>
          <dd>
            {SYSTEM_LABEL[job.system] ?? job.system}
            {job.system === "greenhouse" && !job.closed_at && (
              <>
                {" "}
                <Link to={`/jobs/${job.id}`} className="hint">
                  Apply with a pre-filled form
                </Link>
              </>
            )}
          </dd>
        </div>
      </dl>

      {detail.error && <p className="error">{detail.error}</p>}
      {!d && !detail.error && (
        <div className="preview-loading" aria-hidden="true">
          <div className="skeleton h-3 w-11/12" />
          <div className="skeleton h-3 w-10/12" />
          <div className="skeleton h-3 w-9/12" />
        </div>
      )}
      {d &&
        (d.description ? (
          <div className="description">
            <Highlight text={tidyText(d.description)} pattern={pattern} />
          </div>
        ) : (
          <p className="hint">
            {d.system === "workday"
              ? "The full description is fetched on a later scan. Open the posting to read it now."
              : "This job board doesn't include descriptions. Open the posting to read it."}
          </p>
        ))}
    </motion.article>
  );
}
