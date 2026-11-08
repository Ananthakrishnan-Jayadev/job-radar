import { ExternalLink } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import Chips from "../components/Chips";
import RemoveCompanies, { removedText } from "../components/RemoveCompanies";
import SortHeader, { useSort, type Sort } from "../components/SortHeader";
import TaskStatus from "../components/TaskStatus";
import { COMPANY_STATUS_LABEL, CONFIDENCE_LABEL, SIZE_LABEL, SYSTEM_LABEL, boardLabel, formatCount } from "../format";
import { getList, toggleInList, withParam } from "../params";
import { useApp, useLoad } from "../state";
import type { Company, CompanyStatus, DetectedBoard } from "../types";

const SORT_KEYS = ["name", "wanted", "canada", "total", "size", "boards", "status"] as const;
type SortKey = (typeof SORT_KEYS)[number];

// Size: the head count when known, else the middle of its band; unknown sorts last.
const BAND_SIZE: Record<string, number> = { "<50": 25, "50-199": 125, "200-999": 600, "1000-4999": 3000, "5000+": 10000 };
const sizeOf = (c: Company) => c.employee_count ?? BAND_SIZE[c.size_band] ?? -1;
// Status: the ones you care about first.
const STATUS_ORDER: Record<CompanyStatus, number> = { target: 0, watching: 1, none: 2, ignored: 3 };
// Job boards: by the first board's system name, so companies on the same
// system sit together; companies with no board of their own come first.
const boardsOf = (c: Company) =>
  c.boards
    .filter((b) => b.system !== "manual" && (b.enabled || b.system !== "adzuna"))
    .map((b) => SYSTEM_LABEL[b.system] ?? b.system)
    .sort()
    .join(" ");

function compare(a: Company, b: Company, { key, dir }: Sort<SortKey>): number {
  const by: Record<SortKey, number> = {
    name: a.name.localeCompare(b.name, "en-CA", { sensitivity: "base" }),
    wanted: a.wanted_open - b.wanted_open,
    canada: a.canada_open - b.canada_open,
    total: (a.total_open ?? -1) - (b.total_open ?? -1),
    size: sizeOf(a) - sizeOf(b),
    boards: boardsOf(a).localeCompare(boardsOf(b)),
    status: STATUS_ORDER[a.status] - STATUS_ORDER[b.status],
  };
  const order = dir === "asc" ? by[key] : -by[key];
  // Ties: more matching roles first, then by name.
  return order || b.wanted_open - a.wanted_open || a.name.localeCompare(b.name);
}

export default function CompaniesPage() {
  const { meta, dataVersion, task, watchTask, refresh } = useApp();
  const [bulkBusy, setBulkBusy] = useState(false);
  // Companies whose status just changed: their status cell flashes once.
  const [changed, setChanged] = useState<Set<number>>(new Set());
  const changedTimer = useRef<number>();
  function flash(ids: number[]) {
    setChanged(new Set(ids));
    window.clearTimeout(changedTimer.current);
    changedTimer.current = window.setTimeout(() => setChanged(new Set()), 900);
  }
  const [taskError, setTaskError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const companies = useLoad(() => api.companies(params), `${params}|${dataVersion}`);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [sort, sortBy] = useSort<SortKey>("jobradar-companies-sort", { key: "wanted", dir: "desc" }, SORT_KEYS);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [removing, setRemoving] = useState(false);
  // What the last removal did (also set when a company page removed one).
  const location = useLocation();
  const [removedNote, setRemovedNote] = useState<string | null>(
    (location.state as { removed?: string } | null)?.removed ?? null,
  );

  const rows = [...(companies.data ?? [])].sort((a, b) => compare(a, b, sort));

  async function fillSizes() {
    setTaskError(null);
    try {
      watchTask(await api.fillAllSizes());
    } catch (err) {
      setTaskError(err instanceof Error ? err.message : String(err));
    }
  }

  async function findBoards() {
    setTaskError(null);
    try {
      watchTask(await api.findMissingBoards());
    } catch (err) {
      setTaskError(err instanceof Error ? err.message : String(err));
    }
  }

  // Only ticks on companies still listed count (a filter may hide some).
  const tickedRows = rows.filter((c) => ticked.has(c.id));
  const allTicked = rows.length > 0 && tickedRows.length === rows.length;

  function tick(id: number) {
    setTicked((was) => {
      const next = new Set(was);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  /** Set one status on every ticked company. */
  async function setStatusAll(status: CompanyStatus) {
    setBulkBusy(true);
    setTaskError(null);
    try {
      const done = await Promise.all(tickedRows.map((c) => api.patchCompany(c.id, { status })));
      const byId = new Map(done.map((c) => [c.id, c]));
      companies.setData((list) => list?.map((c) => byId.get(c.id) ?? c));
      flash(done.map((c) => c.id));
      setRemovedNote(`${COMPANY_STATUS_LABEL[status]}: ${done.length === 1 ? done[0].name : `${done.length} companies`}.`);
      setTicked(new Set());
    } catch (err) {
      setTaskError(err instanceof Error ? err.message : String(err));
    } finally {
      setBulkBusy(false);
    }
  }

  const withoutBoard = (companies.data ?? []).filter((c) => c.boards.every((b) => b.system === "manual")).length;

  async function setStatus(company: Company, status: CompanyStatus) {
    const updated = await api.patchCompany(company.id, { status });
    companies.setData((list) => list?.map((c) => (c.id === updated.id ? updated : c)));
    flash([updated.id]);
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
        <button type="button" disabled={task?.running} onClick={fillSizes}>
          Fill in company sizes
        </button>
        {withoutBoard > 0 && (
          <button type="button" disabled={task?.running} onClick={findBoards}>
            Find job boards for {withoutBoard} companies
          </button>
        )}
      </div>
      <TaskStatus name="sizes" />
      <TaskStatus name="find-boards" />
      {taskError && <p className="error" role="alert">{taskError}</p>}

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
      {removedNote && (
        <motion.p
          key={removedNote}
          className="notice removed-note"
          role="status"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          {removedNote}
        </motion.p>
      )}

      <AnimatePresence initial={false}>
      {tickedRows.length > 0 && !removing && (
        <motion.div
          key="bulk"
          className="bulk-bar companies-bulk"
          role="group"
          aria-label="Ticked companies"
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
        >
          <span>{tickedRows.length} ticked</span>
          <label className="bulk-status">
            <span className="sr-only">Set the status of the ticked companies</span>
            <select
              value=""
              disabled={bulkBusy}
              onChange={(e) => e.target.value && setStatusAll(e.target.value as CompanyStatus)}
            >
              <option value="">Set status…</option>
              {(Object.keys(COMPANY_STATUS_LABEL) as CompanyStatus[]).map((s) => (
                <option key={s} value={s}>
                  {COMPANY_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <button type="button" disabled={bulkBusy} onClick={() => setRemoving(true)}>
            Remove {tickedRows.length === 1 ? "company" : `${tickedRows.length} companies`}
          </button>
          <button type="button" className="link" onClick={() => setTicked(new Set())}>
            Untick all
          </button>
        </motion.div>
      )}
      </AnimatePresence>
      {removing && tickedRows.length > 0 && (
        <RemoveCompanies
          companies={tickedRows}
          onRemoved={(result) => {
            const gone = new Set(result.removed.map((c) => c.id));
            companies.setData((list) => list?.filter((c) => !gone.has(c.id)));
            setTicked((was) => new Set([...was].filter((id) => !gone.has(id))));
            setRemovedNote(removedText(result) || null);
            // The Jobs page and its counts lose those companies' jobs.
            if (result.removed.length) refresh();
          }}
          onClose={() => {
            setRemoving(false);
            setTicked(new Set());
          }}
        />
      )}

      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="companies">
            <thead>
              <tr>
                <th scope="col" className="tick-col">
                  <input
                    type="checkbox"
                    aria-label={allTicked ? "Untick all companies" : "Tick all companies shown"}
                    checked={allTicked}
                    ref={(el) => {
                      if (el) el.indeterminate = tickedRows.length > 0 && !allTicked;
                    }}
                    onChange={() => setTicked(allTicked ? new Set() : new Set(rows.map((c) => c.id)))}
                  />
                </th>
                <SortHeader sortKey="name" first="asc" sort={sort} onSort={sortBy}>
                  Company
                </SortHeader>
                <SortHeader
                  sortKey="wanted"
                  first="desc"
                  sort={sort}
                  onSort={sortBy}
                  className="num"
                  title="Open jobs in Canada in your role groups (roles.toml)"
                >
                  Matching roles
                </SortHeader>
                <SortHeader sortKey="canada" first="desc" sort={sort} onSort={sortBy} className="num">
                  Open in Canada
                </SortHeader>
                <SortHeader sortKey="total" first="desc" sort={sort} onSort={sortBy} className="num">
                  Open worldwide
                </SortHeader>
                <SortHeader sortKey="size" first="desc" sort={sort} onSort={sortBy}>
                  Size
                </SortHeader>
                <SortHeader sortKey="boards" first="asc" sort={sort} onSort={sortBy}>
                  Job boards
                </SortHeader>
                <SortHeader sortKey="status" first="asc" sort={sort} onSort={sortBy}>
                  Status
                </SortHeader>
              </tr>
            </thead>
            <tbody>
              {/* Rows slide to their new place when the sort changes; removed ones fade out. */}
              <AnimatePresence initial={false}>
              {rows.map((c) => (
                <motion.tr
                  key={c.id}
                  layout="position"
                  exit={{ opacity: 0, transition: { duration: 0.2 } }}
                  transition={{ layout: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } }}
                  className={`${c.status === "ignored" ? "is-closed" : ""}${ticked.has(c.id) ? " ticked" : ""}`}
                >
                  <td className="tick-col">
                    <input
                      type="checkbox"
                      aria-label={`Tick ${c.name}`}
                      checked={ticked.has(c.id)}
                      onChange={() => tick(c.id)}
                    />
                  </td>
                  <td>
                    <div className="company-name">
                      <Link to={`/companies/${c.id}`} className="job-title">
                        {c.name}
                      </Link>
                      {c.careers_page && (
                        <a
                          className="careers-link"
                          href={c.careers_page}
                          target="_blank"
                          rel="noreferrer"
                          title={c.careers_page}
                          aria-label={`${c.name} careers page (opens in a new tab)`}
                        >
                          Careers
                          <ExternalLink size={12} aria-hidden="true" />
                        </a>
                      )}
                    </div>
                    {!c.canadian && <span className="hint">Global</span>}
                  </td>
                  <td className="num">
                    {c.wanted_open > 0 ? <Link to={`/?company=${c.id}&include_ignored=1`}>{formatCount(c.wanted_open)}</Link> : "0"}
                  </td>
                  <td className="num">
                    {c.canada_open > 0 ? (
                      <Link to={`/?company=${c.id}&include_ignored=1&all_roles=1`}>{formatCount(c.canada_open)}</Link>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td className="num">{formatCount(c.total_open)}</td>
                  <td className="nowrap">{SIZE_LABEL[c.size_band] ?? c.size_band}</td>
                  <td>
                    {c.boards.every((b) => b.system === "manual") && <span className="tag warn">No job board yet</span>}
                    {/* A switched-off Adzuna snapshot is history, not a board: leave it out here. */}
                    {c.boards.filter((b) => b.enabled || b.system !== "adzuna").map((b) => (
                      <span
                        key={b.id}
                        className={`tag${b.last_error ? " error" : !b.confirmed ? " warn" : ""}${b.enabled || b.system === "manual" ? "" : " off"}`}
                        title={b.last_error ?? (b.confirmed ? b.slug_or_url : "Matched by name; not confirmed")}
                      >
                        {SYSTEM_LABEL[b.system] ?? b.system}
                      </span>
                    ))}
                  </td>
                  <td className={changed.has(c.id) ? "just-changed" : undefined}>
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
                </motion.tr>
              ))}
              </AnimatePresence>
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
  const [careersUrl, setCareersUrl] = useState("");
  const [system, setSystem] = useState("");
  const [board, setBoard] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<DetectedBoard[] | null>(null);
  const [finding, setFinding] = useState(false);

  async function find() {
    setFinding(true);
    setError(null);
    try {
      const found = await api.detect({ name, careers_url: careersUrl || null, canadian });
      setOptions(found);
      if (found.length > 0) {
        setSystem(found[0].system);
        setBoard(found[0].slug_or_url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setFinding(false);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const company = await api.addCompany({
        name,
        canadian,
        careers_url: careersUrl || null,
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
        <label className="stack grow">
          Careers page (optional)
          <input
            type="url"
            value={careersUrl}
            placeholder="https://company.com/careers"
            onChange={(e) => setCareersUrl(e.target.value)}
          />
        </label>
        <button type="button" disabled={!name || finding} onClick={find}>
          {finding ? "Looking…" : "Find its job board"}
        </button>
      </div>
      {options && options.length === 0 && (
        <p className="hint">No job board found. Pick the system and enter the board below, or add it later.</p>
      )}
      {options && options.length > 0 && (
        <fieldset className="options">
          <legend>Job boards found</legend>
          {options.map((o) => (
            <label key={`${o.system}:${o.slug_or_url}`} className="check">
              <input
                type="radio"
                name="found-board"
                checked={system === o.system && board === o.slug_or_url}
                onChange={() => {
                  setSystem(o.system);
                  setBoard(o.slug_or_url);
                }}
              />
              {boardLabel(o.system, o.slug_or_url)}
              <span className="hint">
                {CONFIDENCE_LABEL[o.confidence]}
                {o.note && `: ${o.note}`}
              </span>
            </label>
          ))}
        </fieldset>
      )}
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
