import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { COMPANY_STATUS_LABEL, SIZE_LABEL, SYSTEM_LABEL, boardLabel, formatCount, formatDateTime } from "../format";
import { useApp, useLoad } from "../state";
import type { Company, CompanyStatus } from "../types";

const SIZE_SOURCE: Record<string, string> = {
  manual: "entered by you",
  wikidata: "from Wikidata",
  estimate: "estimated",
  stillhiring: "from stillhiring.today",
};

export default function CompanyPage() {
  const id = Number(useParams().id);
  const { meta, scan, startScan, dataVersion } = useApp();
  const company = useLoad(() => api.company(id), `${id}|${dataVersion}`);
  const [error, setError] = useState<string | null>(null);

  if (company.error) return <p className="error" role="alert">{company.error}</p>;
  if (!company.data) return <p className="loading">Loading…</p>;
  const c = company.data;

  async function patch(change: Parameters<typeof api.patchCompany>[1]) {
    setError(null);
    try {
      company.setData(await api.patchCompany(id, change));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function toggleBoard(boardId: number, change: { enabled?: boolean; confirmed?: boolean }) {
    await api.patchBoard(boardId, change);
    company.reload();
  }

  return (
    <article className="company-page">
      <Link to="/companies" className="back">
        All companies
      </Link>
      <header className="job-head">
        <h1>{c.name}</h1>
        <p className="job-sub">
          <span>{c.canadian ? "Canadian company" : "Global company"}</span>
          <Link to={`/?company=${c.id}&include_ignored=1`}>
            {formatCount(c.canada_open)} open {c.canada_open === 1 ? "job" : "jobs"} in Canada
          </Link>
          {c.total_open !== null && <span>{formatCount(c.total_open)} worldwide</span>}
        </p>
      </header>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="job-columns">
        <div className="job-main">
          <section>
            <h2>Job boards</h2>
            <table className="boards">
              <thead>
                <tr>
                  <th scope="col">Board</th>
                  <th scope="col">Last scan</th>
                  <th scope="col" className="num">Open</th>
                  <th scope="col">Scanned</th>
                </tr>
              </thead>
              <tbody>
                {c.boards.map((b) => (
                  <tr key={b.id} className={b.enabled ? "" : "is-closed"}>
                    <td>
                      {boardLabel(b.system, b.slug_or_url)}
                      {!b.confirmed && (
                        <div className="notice small">
                          Matched by name only.{" "}
                          <button type="button" className="link" onClick={() => toggleBoard(b.id, { confirmed: true })}>
                            It's the right company
                          </button>
                        </div>
                      )}
                      {b.last_error && <div className="error small">{b.last_error}</div>}
                    </td>
                    <td className="nowrap">{formatDateTime(b.last_scanned_at)}</td>
                    <td className="num">{formatCount(b.total_open)}</td>
                    <td>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={b.enabled}
                          onChange={(e) => toggleBoard(b.id, { enabled: e.target.checked })}
                        />
                        {b.enabled ? "Yes" : "No"}
                      </label>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {c.boards.length === 0 && <p className="hint">No job board yet. Add one below to start scanning.</p>}
            <AddBoard company={c} systems={meta?.systems ?? []} onAdded={(updated) => company.setData(updated)} />
            <button
              type="button"
              disabled={scan?.running || c.boards.every((b) => !b.enabled)}
              onClick={() => startScan(c.id)}
            >
              Scan {c.name} now
            </button>
          </section>
        </div>

        <aside className="job-side">
          <section className="panel">
            <h2>My tracking</h2>
            <label className="stack">
              Status
              <select value={c.status} onChange={(e) => patch({ status: e.target.value as CompanyStatus })}>
                {(Object.keys(COMPANY_STATUS_LABEL) as CompanyStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {COMPANY_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </label>
            {c.status === "ignored" && <p className="hint">Its jobs are hidden from the jobs list.</p>}
            <CompanySize company={c} onSave={(n) => patch({ employee_count: n })} />
            <CompanyNotes company={c} onSave={(notes) => patch({ notes })} />
          </section>
        </aside>
      </div>
    </article>
  );
}

function CompanySize({ company, onSave }: { company: Company; onSave: (n: number | null) => void }) {
  const [value, setValue] = useState(company.employee_count?.toString() ?? "");
  useEffect(() => setValue(company.employee_count?.toString() ?? ""), [company.employee_count]);
  const parsed = value.trim() === "" ? null : Number(value.replace(/[,\s]/g, ""));
  const valid = parsed === null || (Number.isInteger(parsed) && parsed >= 0);
  const changed = parsed !== company.employee_count;

  return (
    <div className="stack">
      <label htmlFor="size">Employees</label>
      <div className="row">
        <input id="size" inputMode="numeric" value={value} placeholder="e.g. 450" onChange={(e) => setValue(e.target.value)} />
        <button type="button" className="primary" disabled={!valid || !changed} onClick={() => onSave(parsed)}>
          Save size
        </button>
      </div>
      <p className="hint">
        {SIZE_LABEL[company.size_band] ?? company.size_band}
        {company.size_source && `, ${SIZE_SOURCE[company.size_source] ?? company.size_source}`}.
        {!valid && " Enter a whole number."}
      </p>
    </div>
  );
}

function CompanyNotes({ company, onSave }: { company: Company; onSave: (notes: string) => void }) {
  const [text, setText] = useState(company.notes);
  useEffect(() => setText(company.notes), [company.notes]);
  return (
    <div className="stack">
      <label htmlFor="company-notes">Notes</label>
      <textarea id="company-notes" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="row">
        <button type="button" className="primary" disabled={text === company.notes} onClick={() => onSave(text)}>
          Save notes
        </button>
      </div>
    </div>
  );
}

function AddBoard({ company, systems, onAdded }: { company: Company; systems: string[]; onAdded: (c: Company) => void }) {
  const [system, setSystem] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      onAdded(await api.addBoard(company.id, { system, slug_or_url: value }));
      setSystem("");
      setValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <form className="add-board" onSubmit={add}>
      <div className="row">
        <select aria-label="Job system" required value={system} onChange={(e) => setSystem(e.target.value)}>
          <option value="">Add a job board…</option>
          {systems.map((s) => (
            <option key={s} value={s}>
              {SYSTEM_LABEL[s] ?? s}
            </option>
          ))}
        </select>
        {system && (
          <>
            <input
              required
              className="grow"
              aria-label="Board name or link"
              value={value}
              placeholder={system === "workday" ? "https://company.wd3.myworkdayjobs.com/Careers" : "Board name or link"}
              onChange={(e) => setValue(e.target.value)}
            />
            <button type="submit" className="primary">
              Add board
            </button>
          </>
        )}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
