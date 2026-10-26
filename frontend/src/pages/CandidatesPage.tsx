import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import TaskStatus from "../components/TaskStatus";
import { SIZE_LABEL, boardLabel, formatCount, formatDateTime } from "../format";
import { withParam } from "../params";
import { useApp, useLoad } from "../state";
import type { Candidate } from "../types";

const TABS = [
  { value: "pending", label: "To review" },
  { value: "approved", label: "Added" },
  { value: "rejected", label: "Rejected" },
];

export default function CandidatesPage() {
  const { dataVersion, task, watchTask } = useApp();
  const [params, setParams] = useSearchParams();
  const decision = params.get("decision") ?? "pending";
  const list = useLoad(() => api.candidates(params), `${params}|${dataVersion}`);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      const s = await api.refreshCandidates();
      setMessage(
        `Read ${formatCount(s.total)} companies (${formatCount(s.canadian)} based in Canada): ` +
          `${formatCount(s.new)} new, ${formatCount(s.gone)} no longer listed. ` +
          `${s.linked} were already on your list; ${s.sizes} company sizes updated.`,
      );
      list.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  }

  async function findAll() {
    setError(null);
    try {
      watchTask(await api.detectAllCandidates());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const items = list.data?.items ?? [];
  const missingBoards = items.filter((c) => !c.detected_system && !c.detect_note && !c.gone_at).length;

  return (
    <div className="candidates-page">
      <div className="results-head">
        <h1>Candidates</h1>
        <button type="button" className="primary" disabled={refreshing} onClick={refresh}>
          {refreshing ? "Reading stillhiring.today…" : "Refresh from stillhiring.today"}
        </button>
      </div>
      <p className="lead">
        Companies listed on <a href="https://stillhiring.today/" target="_blank" rel="noreferrer">stillhiring.today</a> as
        actively hiring. Add the ones worth scanning: only their jobs in Canada will show up.
        {list.data?.refreshed_at && ` Last read ${formatDateTime(list.data.refreshed_at)}.`}
      </p>
      {message && <p className="task-status done">{message}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={decision === t.value}
            className={decision === t.value ? "on" : ""}
            onClick={() => setParams(withParam(params, "decision", t.value === "pending" ? null : t.value))}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="filter-row">
        <label className="check">
          <input
            type="checkbox"
            checked={params.get("scope") === "readable"}
            onChange={(e) => setParams(withParam(params, "scope", e.target.checked ? "readable" : null))}
          />
          Also show companies based elsewhere whose job board we can read (many have Canadian offices)
        </label>
        {decision === "pending" && missingBoards > 0 && (
          <button type="button" disabled={task?.running} onClick={findAll}>
            Find job boards for {missingBoards} companies
          </button>
        )}
      </div>
      <TaskStatus name="boards" />

      {list.error && <p className="error" role="alert">{list.error}</p>}
      {list.data && items.length === 0 && (
        <p className="empty">
          {list.data.refreshed_at
            ? "Nothing here. Try another tab, or include companies based elsewhere."
            : "No candidates yet. Refresh from stillhiring.today to load them."}
        </p>
      )}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="candidates">
            <thead>
              <tr>
                <th scope="col">Company</th>
                <th scope="col">Based in</th>
                <th scope="col">Size</th>
                <th scope="col">Job board</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <CandidateRow key={c.id} candidate={c} onChange={list.reload} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CandidateRow({ candidate: c, onChange }: { candidate: Candidate; onChange: () => void }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const hq = [c.hq_city, c.hq_province ?? c.hq_country].filter(Boolean).join(", ");
  return (
    <tr className={c.gone_at ? "is-closed" : ""}>
      <td>
        <span className="job-title">{c.name}</span>
        {c.tagline && <span className="tagline">{c.tagline}</span>}
        {c.gone_at && <span className="tag">No longer listed</span>}
      </td>
      <td>{hq || "—"}</td>
      <td className="nowrap">{c.employees ? `${formatCount(c.employees)} (${SIZE_LABEL[c.size_band]})` : "—"}</td>
      <td>
        {c.detected_system && c.detected_slug ? (
          <>
            {boardLabel(c.detected_system, c.detected_slug)}
            {c.detect_note && <span className="hint block">{c.detect_note}</span>}
          </>
        ) : (
          <>
            <span className="hint">{c.detect_note ?? "Not found yet"}</span>
            {c.decision === "pending" && (
              <button type="button" className="link block" disabled={busy !== null}
                onClick={() => act("find", () => api.detectCandidate(c.id))}>
                {busy === "find" ? "Looking…" : "Find its job board"}
              </button>
            )}
          </>
        )}
        {c.jobs_url && (
          <a className="hint block" href={c.jobs_url} target="_blank" rel="noreferrer">
            Careers page
          </a>
        )}
      </td>
      <td className="actions">
        {c.decision === "pending" && (
          <>
            <button type="button" className="primary" disabled={busy !== null}
              onClick={() => act("add", async () => {
                const { company_id } = await api.approveCandidate(c.id);
                if (!c.detected_system) navigate(`/companies/${company_id}`);
              })}>
              {c.detected_system ? "Add to my list" : "Add without a board"}
            </button>
            <button type="button" disabled={busy !== null} onClick={() => act("reject", () => api.rejectCandidate(c.id))}>
              Not interested
            </button>
          </>
        )}
        {c.decision === "approved" && c.company_id && <Link to={`/companies/${c.company_id}`}>Open company</Link>}
        {c.decision === "rejected" && (
          <button type="button" disabled={busy !== null} onClick={() => act("restore", () => api.restoreCandidate(c.id))}>
            Move back to review
          </button>
        )}
        {error && <span className="error-inline block" role="alert">{error}</span>}
      </td>
    </tr>
  );
}
