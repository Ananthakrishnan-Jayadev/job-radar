import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import Chips from "../components/Chips";
import { COMPANY_STATUS_LABEL, SIZE_LABEL, SYSTEM_LABEL, formatCount } from "../format";
import { getList, toggleInList, withParam } from "../params";
import { useApp, useLoad } from "../state";
import type { Company, CompanyStatus } from "../types";

export default function CompaniesPage() {
  const { meta, dataVersion } = useApp();
  const [params, setParams] = useSearchParams();
  const companies = useLoad(() => api.companies(params), `${params}|${dataVersion}`);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [sortByRoles, setSortByRoles] = useState(true);

  const rows = [...(companies.data ?? [])].sort((a, b) =>
    sortByRoles ? b.canada_open - a.canada_open || a.name.localeCompare(b.name) : a.name.localeCompare(b.name),
  );

  async function setStatus(company: Company, status: CompanyStatus) {
    const updated = await api.patchCompany(company.id, { status });
    companies.setData((list) => list?.map((c) => (c.id === updated.id ? updated : c)));
  }

  return (
    <div className="companies-page">
      <div className="results-head">
        <h1>{companies.data ? `${formatCount(companies.data.length)} companies` : "Companies"}</h1>
        <form
          className="inline-search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            setParams(withParam(params, "q", query.trim() || null));
          }}
        >
          <input type="search" value={query} placeholder="Find a company" onChange={(e) => setQuery(e.target.value)} />
        </form>
        <label className="sort">
          Sort
          <select value={sortByRoles ? "roles" : "name"} onChange={(e) => setSortByRoles(e.target.value === "roles")}>
            <option value="roles">Most Canadian roles</option>
            <option value="name">Name A–Z</option>
          </select>
        </label>
      </div>

      {meta && (
        <div className="filter-bar">
          <Chips
            legend="Size"
            options={meta.size_bands.map((b) => ({ value: b, label: SIZE_LABEL[b] ?? b }))}
            selected={getList(params, "sizes")}
            onToggle={(v) => setParams(toggleInList(params, "sizes", v))}
          />
          <Chips
            legend="Status"
            options={meta.company_statuses.map((s) => ({ value: s, label: COMPANY_STATUS_LABEL[s] }))}
            selected={getList(params, "status")}
            onToggle={(v) => setParams(toggleInList(params, "status", v))}
          />
        </div>
      )}

      <AddCompany systems={meta?.systems ?? []} />

      {companies.error && <p className="error" role="alert">{companies.error}</p>}
      {companies.data && rows.length === 0 && (
        <p className="empty">No companies match. Clear the filters, or add one above.</p>
      )}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="companies">
            <thead>
              <tr>
                <th scope="col">Company</th>
                <th scope="col" className="num">Open in Canada</th>
                <th scope="col" className="num">Open worldwide</th>
                <th scope="col">Size</th>
                <th scope="col">Job boards</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className={c.status === "ignored" ? "is-closed" : ""}>
                  <td>
                    <Link to={`/companies/${c.id}`} className="job-title">
                      {c.name}
                    </Link>
                    {!c.canadian && <span className="hint"> Global</span>}
                  </td>
                  <td className="num">
                    {c.canada_open > 0 ? (
                      <Link to={`/?company=${c.id}&include_ignored=1`}>{formatCount(c.canada_open)}</Link>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td className="num">{formatCount(c.total_open)}</td>
                  <td className="nowrap">{SIZE_LABEL[c.size_band] ?? c.size_band}</td>
                  <td>
                    {c.boards.map((b) => (
                      <span
                        key={b.id}
                        className={`tag${b.last_error ? " error" : !b.confirmed ? " warn" : ""}${b.enabled ? "" : " off"}`}
                        title={b.last_error ?? (b.confirmed ? b.slug_or_url : "Matched by name; not confirmed")}
                      >
                        {SYSTEM_LABEL[b.system] ?? b.system}
                      </span>
                    ))}
                  </td>
                  <td>
                    <select
                      aria-label={`Status for ${c.name}`}
                      value={c.status}
                      onChange={(e) => setStatus(c, e.target.value as CompanyStatus)}
                    >
                      {(Object.keys(COMPANY_STATUS_LABEL) as CompanyStatus[]).map((s) => (
                        <option key={s} value={s}>
                          {COMPANY_STATUS_LABEL[s]}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AddCompany({ systems }: { systems: string[] }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [canadian, setCanadian] = useState(true);
  const [system, setSystem] = useState("");
  const [board, setBoard] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const company = await api.addCompany({
        name,
        canadian,
        board: system && board ? { system, slug_or_url: board } : undefined,
      });
      navigate(`/companies/${company.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  if (!open) {
    return (
      <button type="button" className="add-toggle" onClick={() => setOpen(true)}>
        Add a company
      </button>
    );
  }
  return (
    <form className="panel add-company" onSubmit={add}>
      <h2>Add a company</h2>
      <label className="stack">
        Name
        <input required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="check">
        <input type="checkbox" checked={canadian} onChange={(e) => setCanadian(e.target.checked)} />
        Canadian company (its plain "Remote" postings count as Canada)
      </label>
      <div className="row">
        <label className="stack">
          Job system
          <select value={system} onChange={(e) => setSystem(e.target.value)}>
            <option value="">Add later</option>
            {systems.map((s) => (
              <option key={s} value={s}>
                {SYSTEM_LABEL[s] ?? s}
              </option>
            ))}
          </select>
        </label>
        {system && (
          <label className="stack grow">
            Board name or link
            <input
              required
              value={board}
              placeholder={system === "workday" ? "https://company.wd3.myworkdayjobs.com/Careers" : "e.g. jobs.ashbyhq.com/cohere"}
              onChange={(e) => setBoard(e.target.value)}
            />
          </label>
        )}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button type="submit" className="primary">
          Add company
        </button>
        <button type="button" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
