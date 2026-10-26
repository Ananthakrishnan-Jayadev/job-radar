import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import JobFilters from "../components/JobFilters";
import Pagination from "../components/Pagination";
import StatusSelect from "../components/StatusSelect";
import { SIZE_LABEL, formatCount, formatDate } from "../format";
import { savedFilters, withParam } from "../params";
import { useApp, useLoad } from "../state";
import type { JobSummary } from "../types";

const SORTS = [
  { value: "", label: "Best match, then newest" },
  { value: "posted", label: "Newest posted" },
  { value: "first_seen", label: "Newest found" },
  { value: "company", label: "Company A–Z" },
  { value: "title", label: "Title A–Z" },
];

export default function JobsPage() {
  const { meta, previousVisit, dataVersion } = useApp();
  const [params, setParams] = useSearchParams();
  const key = `${params}|${dataVersion}`;

  const jobs = useLoad(() => api.jobs(params), key);
  const counts = useLoad(() => api.provinceCounts(params), key);

  function sortBy(value: string) {
    let next = withParam(params, "sort", value || null);
    next = withParam(next, "order", value === "company" || value === "title" ? "asc" : null);
    setParams(next);
  }

  function updateJob(id: number, change: Partial<JobSummary>) {
    jobs.setData((page) =>
      page ? { ...page, items: page.items.map((j) => (j.id === id ? { ...j, ...change } : j)) } : page,
    );
  }

  const isNew = (job: JobSummary) => previousVisit !== null && job.first_seen > previousVisit;

  return (
    <div className="jobs-layout">
      {meta && (
        <JobFilters
          meta={meta}
          params={params}
          setParams={setParams}
          provinceCounts={counts.data}
          previousVisit={previousVisit}
        />
      )}

      <section className="results" aria-busy={jobs.loading}>
        <div className="results-head">
          <h1>{jobs.data ? `${formatCount(jobs.data.total)} ${jobs.data.total === 1 ? "job" : "jobs"}` : "Jobs"}</h1>
          <label className="sort">
            Sort
            <select value={params.get("sort") ?? ""} onChange={(e) => sortBy(e.target.value)}>
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <SaveSearch params={params} />
          <a className="button" href={api.exportUrl(params)} download>
            Export CSV
          </a>
        </div>

        {jobs.error && (
          <p className="error" role="alert">
            {jobs.error}
          </p>
        )}

        {jobs.data && jobs.data.items.length === 0 && !jobs.loading && (
          <div className="empty">
            {meta && meta.open_jobs === 0 ? (
              <p>No jobs yet. Run a scan to fetch jobs from the companies on your list.</p>
            ) : (
              <p>No jobs match these filters. Try fewer words, more provinces, or a longer time window.</p>
            )}
          </div>
        )}

        {jobs.data && jobs.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="jobs">
              <thead>
                <tr>
                  <th scope="col">Job</th>
                  <th scope="col">Where</th>
                  <th scope="col">Size</th>
                  <th scope="col">Posted</th>
                  <th scope="col">Salary</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.items.map((job) => (
                  <tr key={job.id} className={`${isNew(job) ? "is-new" : ""}${job.closed_at ? " is-closed" : ""}`}>
                    <td className="job-cell">
                      <Link to={`/jobs/${job.id}`} className="job-title">
                        {job.title}
                      </Link>
                      <span className="job-company">
                        <Link to={`/companies/${job.company_id}`}>{job.company}</Link>
                        {isNew(job) && <span className="tag new">New</span>}
                        {job.closed_at && <span className="tag">Closed</span>}
                        {!job.board_confirmed && (
                          <span className="tag warn" title="This board was matched by name and isn't confirmed yet">
                            Unconfirmed
                          </span>
                        )}
                      </span>
                    </td>
                    <td>{job.location}</td>
                    <td className="nowrap">{SIZE_LABEL[job.size_band] ?? job.size_band}</td>
                    <td className="nowrap num">{formatDate(job.posted_at ?? job.first_seen)}</td>
                    <td className="salary">{job.salary ?? ""}</td>
                    <td>
                      <StatusSelect
                        jobId={job.id}
                        status={job.status}
                        onChange={(t) => updateJob(job.id, { status: t.status, applied_at: t.applied_at })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {jobs.data && (
          <Pagination
            page={jobs.data.page}
            pageSize={jobs.data.page_size}
            total={jobs.data.total}
            onPage={(p) => {
              setParams(withParam(params, "page", p > 1 ? String(p) : null));
              window.scrollTo({ top: 0 });
            }}
          />
        )}
      </section>
    </div>
  );
}

/** Save the current search and filters under a name. */
function SaveSearch({ params }: { params: URLSearchParams }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await api.saveSearch({
        name,
        query: params.get("q") ?? "",
        filters: savedFilters(params),
        use_for_sources: false,
      });
      setMessage(`Saved as "${name}".`);
      setOpen(false);
      setName("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  if (!open) {
    return (
      <span className="save-search">
        <button type="button" onClick={() => { setOpen(true); setMessage(null); }}>
          Save search
        </button>
        {message && <span className="hint">{message}</span>}
      </span>
    );
  }
  return (
    <form className="save-search" onSubmit={save}>
      <input autoFocus required value={name} placeholder="Name this search" onChange={(e) => setName(e.target.value)} />
      <button type="submit" className="primary">
        Save
      </button>
      <button type="button" onClick={() => setOpen(false)}>
        Cancel
      </button>
    </form>
  );
}
