import NumberFlow from "@number-flow/react";
import { Bookmark, ChevronRight, CircleCheck, Download, EyeOff, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ActiveFilters from "../components/ActiveFilters";
import { DECISIONS } from "../components/DecisionBar";
import EmptyResults from "../components/EmptyResults";
import JobFilters from "../components/JobFilters";
import JobPreview from "../components/JobPreview";
import Pagination from "../components/Pagination";
import { JOB_STATUS_LABEL, LEVEL_LABEL, SIZE_LABEL, formatDate, levelSourceText, shortLocation } from "../format";
import { normalizeParams } from "../jobFilters";
import { rememberResults, savedFilters, startSearch, withParam } from "../params";
import { useApp, useLoad } from "../state";
import type { JobStatus, JobSummary } from "../types";

const SORTS = [
  { value: "", label: "Best match, then newest" },
  { value: "posted", label: "Newest posted" },
  { value: "first_seen", label: "Newest found" },
  { value: "company", label: "Company A–Z" },
  { value: "title", label: "Title A–Z" },
];

const FILTERS_HIDDEN = "jobradar-filters-hidden";
const UNDO_MS = 8000;

/** Whether the filter column is hidden, remembered in this browser. */
function useFiltersHidden(): [boolean, () => void] {
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem(FILTERS_HIDDEN) === "1";
    } catch {
      return false;
    }
  });
  function toggle() {
    setHidden((was) => {
      try {
        localStorage.setItem(FILTERS_HIDDEN, was ? "0" : "1");
      } catch {
        // Storage refused (private window): it still toggles for this visit.
      }
      return !was;
    });
  }
  return [hidden, toggle];
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return matches;
}

/** Hover text for the level: the years asked and where the level came from. */
function levelTitle(job: JobSummary): string | undefined {
  const parts = [];
  if (job.min_years !== null) parts.push(`Asks for ${job.min_years}+ years`);
  const source = levelSourceText(job.level_source);
  if (job.level && source) parts.push(source);
  return parts.join(", ") || undefined;
}

type Before = Pick<JobSummary, "id" | "status" | "applied_at">;
type Notice = { text: string; before?: Before[]; counted?: number; error?: boolean };

// Jobs taken from "Not reviewed" to a decision in this browser tab, so a long
// session shows how far it got.
const SESSION_KEY = "jobradar-decided";

function readDecided(): number {
  try {
    return Number(sessionStorage.getItem(SESSION_KEY)) || 0;
  } catch {
    return 0;
  }
}

// Typing in a box keeps its keys; a tick box or button doesn't take letters.
const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  ((target instanceof HTMLInputElement && !["checkbox", "radio"].includes(target.type)) ||
    ["TEXTAREA", "SELECT"].includes(target.tagName) ||
    target.isContentEditable);

export default function JobsPage() {
  const { meta, previousVisit, dataVersion } = useApp();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const key = `${params}|${dataVersion}`;

  const jobs = useLoad(() => api.jobs(params), key);
  const counts = useLoad(() => api.provinceCounts(params), key);
  const [filtersHidden, toggleFilters] = useFiltersHidden();
  // Side by side when there's room: the list, and the selected posting beside it.
  const wide = useMediaQuery("(min-width: 1440px)");
  const roomy = useMediaQuery("(min-width: 1100px)");
  const split = wide || (filtersHidden && roomy);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [decided, setDecided] = useState(readDecided);
  const rows = useRef(new Map<number, HTMLLIElement>());
  const lastTicked = useRef<number | null>(null);
  // Moving past the end of a page with J/K opens the next one: which end to land on.
  const landOn = useRef<{ end: "first" | "last"; page: number } | null>(null);

  function countDecided(change: number) {
    setDecided((n) => {
      const next = Math.max(0, n + change);
      try {
        sessionStorage.setItem(SESSION_KEY, String(next));
      } catch {
        // Storage refused: the count still shows for this page.
      }
      return next;
    });
  }

  // The Jobs page opens on your start search, if you picked one (Saved searches).
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    const start = startSearch();
    if (start && params.toString() === "") setParams(new URLSearchParams(start), { replace: true });
  }, []); // once, on arrival

  // Only filters the list understands, each named once (old or hand-made links).
  useEffect(() => {
    if (!meta) return;
    const clean = normalizeParams(meta, params);
    if (clean.toString() !== params.toString()) setParams(clean, { replace: true });
  }, [meta, params]); // setParams is stable enough: a new one never needs a recheck

  useEffect(() => rememberResults(params), [params]);

  // A page that has emptied (its jobs changed status and left the filter, say):
  // go to the last page that still has jobs, instead of showing nothing.
  const data = jobs.data;
  useEffect(() => {
    if (!data || data.page <= 1 || data.items.length) return;
    const last = Math.max(1, Math.ceil(data.total / data.page_size));
    setParams(withParam(params, "page", last > 1 ? String(last) : null), { replace: true });
  }, [data]); // params and setParams change with every page; only new data matters

  // New results: keep the selection if it's still listed, else the first job
  // (side by side) or none; ticks are cleared.
  const items = data?.items ?? [];
  useEffect(() => {
    setChecked(new Set());
    lastTicked.current = null;
    // Wait for the page that was asked for: the old one is still showing at first.
    const land = landOn.current;
    if (land && data?.page !== land.page) return;
    landOn.current = null;
    if (land && items.length) {
      const id = (land.end === "first" ? items[0] : items[items.length - 1]).id;
      setSelectedId(id);
      window.requestAnimationFrame(() => rows.current.get(id)?.scrollIntoView({ block: "nearest" }));
      return;
    }
    setSelectedId((id) => (id !== null && items.some((j) => j.id === id) ? id : split ? items[0]?.id ?? null : null));
  }, [data?.page, data?.total, params.toString()]); // a new page or search, not each status change
  useEffect(() => {
    if (split && selectedId === null && items.length) setSelectedId(items[0].id);
  }, [split]); // entering the split view picks a job to show

  // Undo offers fade after a few seconds.
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), UNDO_MS);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function patchItems(changes: Before[]) {
    const byId = new Map(changes.map((c) => [c.id, c]));
    jobs.setData((page) =>
      page ? { ...page, items: page.items.map((j) => (byId.has(j.id) ? { ...j, ...byId.get(j.id) } : j)) } : page,
    );
  }

  function select(id: number | null, scroll = false) {
    setSelectedId(id);
    if (scroll && id !== null) rows.current.get(id)?.scrollIntoView({ block: "nearest" });
  }

  function move(step: number) {
    if (!items.length || !data) return;
    const at = items.findIndex((j) => j.id === selectedId);
    const pages = Math.ceil(data.total / data.page_size);
    // Past either end of the page: on to the next or previous page.
    if (at === items.length - 1 && step > 0 && data.page < pages) {
      landOn.current = { end: "first", page: data.page + 1 };
      setParams(withParam(params, "page", String(data.page + 1)));
      return;
    }
    if (at === 0 && step < 0 && data.page > 1) {
      landOn.current = { end: "last", page: data.page - 1 };
      setParams(withParam(params, "page", data.page > 2 ? String(data.page - 1) : null));
      return;
    }
    const next = at === -1 ? 0 : Math.min(items.length - 1, Math.max(0, at + step));
    select(items[next].id, true);
  }

  /** Set a status on some jobs; one job decided from the selection moves on to the next. */
  async function decide(ids: number[], status: JobStatus, advance = false) {
    const before = items.filter((j) => ids.includes(j.id)).map(({ id, status, applied_at }) => ({ id, status, applied_at }));
    if (!before.length) return;
    setBusy(true);
    try {
      const done = await Promise.all(ids.map((id) => api.patchJob(id, { status })));
      patchItems(done.map(({ id, status, applied_at }) => ({ id, status, applied_at })));
      const what = ids.length === 1 ? items.find((j) => j.id === ids[0])?.title ?? "1 job" : `${ids.length} jobs`;
      // Reviewed for the first time counts up; taken back to "Not reviewed" counts down.
      const counted =
        status === "new"
          ? -before.filter((b) => b.status !== "new").length
          : before.filter((b) => b.status === "new").length;
      countDecided(counted);
      setNotice({ text: `${JOB_STATUS_LABEL[status]}: ${what}`, before, counted });
      if (ids.length > 1) setChecked(new Set());
      if (advance && ids.length === 1 && ids[0] === selectedId) move(1);
    } catch (err) {
      setNotice({ text: err instanceof Error ? err.message : String(err), error: true });
    } finally {
      setBusy(false);
    }
  }

  async function undo() {
    const before = notice?.before;
    if (!before) return;
    setBusy(true);
    try {
      const done = await Promise.all(
        before.map((b) => api.patchJob(b.id, { status: b.status, applied_at: b.applied_at })),
      );
      patchItems(done.map(({ id, status, applied_at }) => ({ id, status, applied_at })));
      countDecided(-(notice?.counted ?? 0));
      setNotice({ text: "Undone." });
    } catch (err) {
      setNotice({ text: err instanceof Error ? err.message : String(err), error: true });
    } finally {
      setBusy(false);
    }
  }

  // Keys, for working through a list without the mouse. The latest handler
  // is kept in a ref so the listener never sees stale results.
  const onKey = useRef<(e: KeyboardEvent) => void>(() => undefined);
  onKey.current = (e: KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || isTyping(e.target)) return;
    const selected = items.find((j) => j.id === selectedId);
    const k = e.key.toLowerCase();
    if (k === "/") {
      const search = document.getElementById("q");
      if (search) {
        e.preventDefault();
        search.focus();
      }
    } else if (k === "j") move(1);
    else if (k === "k") move(-1);
    else if ((k === "t" || k === " ") && selected) {
      e.preventDefault(); // Space would scroll the page
      toggleCheck(selected.id);
    }
    else if (k === "u") undo();
    else if (k === "escape") setChecked(new Set());
    else if ((k === "o" || (k === "enter" && e.target === document.body)) && selected) navigate(`/jobs/${selected.id}`);
    else {
      const decision = DECISIONS.find((d) => d.key === k);
      if (!decision || busy) return;
      if (checked.size) {
        decide([...checked], decision.status);
      } else if (selected) {
        const next = selected.status === decision.status ? "new" : decision.status;
        decide([selected.id], next, next !== "new");
      }
    }
  };
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey.current(e);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  function sortBy(value: string) {
    let next = withParam(params, "sort", value || null);
    next = withParam(next, "order", value === "company" || value === "title" ? "asc" : null);
    setParams(next);
  }
  // With no words to match, the default order is simply newest first.
  const hasQuery = Boolean(params.get("q"));
  const sorts = hasQuery
    ? SORTS
    : [{ value: "", label: "Newest posted" }, ...SORTS.filter((s) => s.value !== "" && s.value !== "posted")];
  const sortValue = !hasQuery && params.get("sort") === "posted" ? "" : params.get("sort") ?? "";

  // Amber marks what's new since your last visit; when that's every job on
  // the page, one line says so instead of a dot on every row.
  const newSince = (job: JobSummary) => previousVisit !== null && job.first_seen > previousVisit;
  const allNew = items.length > 1 && items.every(newSince);
  const isNew = (job: JobSummary) => !allNew && newSince(job);
  const selected = items.find((j) => j.id === selectedId);

  /** Tick or untick a job; with Shift, tick every job from the last one ticked to this one. */
  function toggleCheck(id: number, range = false) {
    const at = items.findIndex((j) => j.id === id);
    const from = lastTicked.current;
    setChecked((was) => {
      const next = new Set(was);
      if (range && from !== null && from !== at) {
        const [a, b] = from < at ? [from, at] : [at, from];
        for (const job of items.slice(a, b + 1)) next.add(job.id);
      } else if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    lastTicked.current = at;
  }

  return (
    <div className={`jobs-layout${filtersHidden ? " filters-hidden" : ""}`}>
      <a className="skip-link" href="#results">
        Skip to the jobs list
      </a>
      {meta && !filtersHidden && (
        <JobFilters
          meta={meta}
          params={params}
          setParams={setParams}
          provinceCounts={counts.data}
          previousVisit={previousVisit}
        />
      )}

      <section className="results" id="results" tabIndex={-1} aria-busy={jobs.loading}>
        <div className="results-head">
          <button
            type="button"
            className="filters-toggle quiet"
            aria-expanded={!filtersHidden}
            aria-controls="job-filters"
            title={filtersHidden ? "Show the filters" : "Hide the filters to give the list more room"}
            onClick={toggleFilters}
          >
            {filtersHidden ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
            Filters
          </button>
          <h1>
            {data ? (
              <>
                <span aria-hidden="true">
                  <NumberFlow value={data.total} locales="en-CA" /> <small>{data.total === 1 ? "job" : "jobs"}</small>
                </span>
                <span className="sr-only">
                  {data.total.toLocaleString("en-CA")} {data.total === 1 ? "job" : "jobs"}
                </span>
              </>
            ) : (
              "Jobs"
            )}
          </h1>
          {decided > 0 && (
            <span className="session-count" title="Jobs you moved from Not reviewed to a decision in this tab">
              {decided} decided this session
            </span>
          )}
          <label className="sort">
            Sort
            <select value={sortValue} onChange={(e) => sortBy(e.target.value)}>
              {sorts.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <SaveSearch params={params} />
          <a className="button quiet" href={api.exportUrl(params)} download>
            <Download size={15} aria-hidden="true" />
            Export CSV
          </a>
        </div>

        {meta && (
          <ActiveFilters
            meta={meta}
            params={params}
            setParams={setParams}
            companyName={params.has("company") ? items[0]?.company : undefined}
          />
        )}

        {allNew && (
          <p className="all-new">
            <span className="new-dot" aria-hidden="true" />
            Every job on this page is new since your last visit.
          </p>
        )}

        {jobs.error && (
          <p className="error" role="alert">
            Couldn't load the jobs ({jobs.error}). Reload the page; if it keeps happening, the terminal running
            jobradar serve says why.
          </p>
        )}

        {data && items.length === 0 && !jobs.loading && meta && (
          <EmptyResults meta={meta} params={params} setParams={setParams} />
        )}

        {!data && jobs.loading && <SkeletonRows />}

        {items.length > 0 && (
          <div className={`triage${split ? " split" : ""}`}>
            <div className="triage-list">
              {checked.size > 0 && (
                <div className="bulk-bar" role="group" aria-label="Ticked jobs">
                  <span>
                    {checked.size} ticked
                  </span>
                  <button type="button" disabled={busy} onClick={() => decide([...checked], "saved")}>
                    <Bookmark size={14} aria-hidden="true" />
                    Save
                  </button>
                  <button type="button" disabled={busy} onClick={() => decide([...checked], "not_interested")}>
                    <EyeOff size={14} aria-hidden="true" />
                    Not interested
                  </button>
                  <button type="button" disabled={busy} onClick={() => decide([...checked], "applied")}>
                    <CircleCheck size={14} aria-hidden="true" />
                    Applied
                  </button>
                  <button type="button" className="link" onClick={() => setChecked(new Set())}>
                    Untick all
                  </button>
                </div>
              )}

              <BoardHead split={split} />
              <ul className="job-list" aria-label="Jobs">
                {items.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    isNew={isNew(job)}
                    selected={job.id === selectedId}
                    checked={checked.has(job.id)}
                    split={split}
                    busy={busy}
                    rowRef={(el) => {
                      if (el) rows.current.set(job.id, el);
                      else rows.current.delete(job.id);
                    }}
                    onSelect={() => select(job.id)}
                    onCheck={(range) => toggleCheck(job.id, range)}
                    onDecide={(status) => {
                      select(job.id);
                      decide([job.id], status);
                    }}
                  />
                ))}
              </ul>

              <Pagination
                page={data!.page}
                pageSize={data!.page_size}
                total={data!.total}
                onPage={(p) => {
                  setParams(withParam(params, "page", p > 1 ? String(p) : null));
                  window.scrollTo({ top: 0 });
                }}
              />
            </div>

            {split && selected && (
              <JobPreview
                job={selected}
                busy={busy}
                onDecide={(status) => decide([selected.id], status, status !== "new")}
              />
            )}
          </div>
        )}
      </section>

      <AnimatePresence>
        {notice && (
          <motion.div
            key={notice.text}
            className={`toast${notice.error ? " error" : ""}`}
            role={notice.error ? "alert" : "status"}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="toast-text">{notice.text}</span>
            {notice.before && (
              <button type="button" className="link" disabled={busy} onClick={undo}>
                Undo <kbd aria-hidden="true">U</kbd>
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface RowProps {
  job: JobSummary;
  isNew: boolean;
  selected: boolean;
  checked: boolean;
  split: boolean;
  busy: boolean;
  rowRef: (el: HTMLLIElement | null) => void;
  onSelect: () => void;
  onCheck: (range: boolean) => void;
  onDecide: (status: JobStatus) => void;
}

// Company size as a mark: the dot grows with the head count, like a star's
// magnitude on a chart. Unknown is an empty ring.
const SIZE_DOT: Record<string, number> = { "<50": 4, "50-199": 6, "200-999": 8, "1000-4999": 11, "5000+": 14 };

/** The board's column heads; the rows below use the same columns. */
function BoardHead({ split }: { split: boolean }) {
  return (
    <div className="board-head job-row" aria-hidden="true">
      <span className="cell-check" />
      <span className="cell-mark" />
      <span className="cell-posted">Posted</span>
      <span className="cell-job">Job</span>
      <span className="cell-place">Place</span>
      <span className="cell-level">Level</span>
      <span className="cell-size">Size</span>
      <span className="cell-status">Status</span>
      {!split && <span className="row-actions" />}
    </div>
  );
}

/** One job as a line on the board: posted, job and company, place, level, size, status. */
function JobRow({ job, isNew, selected, checked, split, busy, rowRef, onSelect, onCheck, onDecide }: RowProps) {
  // Side by side, a plain click on the title shows the job beside the list;
  // a new-tab click (or any click in the single-column list) opens its page.
  function openTitle(e: MouseEvent) {
    if (split && e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      onSelect();
    }
  }
  const size = SIZE_LABEL[job.size_band] ?? job.size_band;
  const dot = SIZE_DOT[job.size_band];
  const level = job.level ? LEVEL_LABEL[job.level] : null;

  return (
    <li
      ref={rowRef}
      className={`job-row${selected ? " selected" : ""}${checked ? " checked" : ""}${job.status !== "new" ? " decided" : ""}${job.closed_at ? " is-closed" : ""}`}
      aria-current={selected ? "true" : undefined}
      onClick={(e) => {
        if (!(e.target instanceof HTMLElement && e.target.closest("a, button, input, select"))) onSelect();
      }}
    >
      <span className="cell-check">
        <input
          type="checkbox"
          checked={checked}
          aria-label={`Tick ${job.title}`}
          title="Tick (T); Shift-click ticks a range"
          onChange={() => undefined}
          onClick={(e) => onCheck(e.shiftKey)}
        />
      </span>
      <span className="cell-mark">
        {selected ? (
          <ChevronRight size={14} strokeWidth={3} aria-hidden="true" />
        ) : (
          isNew && (
            <span className="new-dot" title="New since your last visit">
              <span className="sr-only">New since your last visit</span>
            </span>
          )
        )}
      </span>
      {job.posted_at ? (
        <time className="cell-posted" dateTime={job.posted_at} title="Posted">
          {formatDate(job.posted_at)}
        </time>
      ) : (
        <time className="cell-posted" dateTime={job.first_seen} title="The posting gives no date: first found then">
          {formatDate(job.first_seen)}
          <small>found</small>
        </time>
      )}
      <div className="cell-job">
        <Link to={`/jobs/${job.id}`} className="job-title" onClick={openTitle}>
          {job.title}
        </Link>
        <div className="row-meta">
          <Link to={`/companies/${job.company_id}`} className="row-company">
            {job.company}
          </Link>
          <span className="inline-place" title={job.location}>
            {shortLocation(job.location)}
          </span>
          {level && (
            <span className="inline-level" title={levelTitle(job)}>
              {level}
            </span>
          )}
          {job.salary && <span className="row-salary">{job.salary}</span>}
          {!job.board_confirmed && (
            <span className="tag warn" title="This board was matched by name and isn't confirmed yet">
              Unconfirmed
            </span>
          )}
        </div>
      </div>
      <span className="cell-place" title={job.location}>
        {shortLocation(job.location)}
      </span>
      <span className="cell-level" title={levelTitle(job)}>
        {level ?? <span className="muted">Not stated</span>}
      </span>
      <span className="cell-size" title={`${size} employees`}>
        <span
          className={`size-dot${dot ? "" : " unknown"}`}
          style={dot ? { width: dot, height: dot } : undefined}
          aria-hidden="true"
        />
        <span className="size-text">{size}</span>
      </span>
      <span className="cell-status">
        {/* A decision stamps into this cell; the row itself never moves. */}
        <AnimatePresence initial={false} mode="popLayout">
          {job.status !== "new" && (
            <motion.span
              key={job.status}
              className={`stamp status-${job.status}`}
              initial={{ opacity: 0, scale: 1.4 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.1 } }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            >
              {JOB_STATUS_LABEL[job.status]}
            </motion.span>
          )}
        </AnimatePresence>
        {job.closed_at && <span className="stamp status-closed">Closed</span>}
      </span>
      {!split && (
        <span className="row-actions">
          {DECISIONS.map(({ status, label, key, icon: Icon }) => (
            <button
              key={status}
              type="button"
              className="quiet"
              disabled={busy}
              aria-pressed={job.status === status}
              aria-label={label}
              title={`${label} (${key.toUpperCase()})`}
              onClick={() => onDecide(job.status === status ? "new" : status)}
            >
              <Icon size={15} aria-hidden="true" />
            </button>
          ))}
        </span>
      )}
    </li>
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
        <button type="button" className="quiet" onClick={() => { setOpen(true); setMessage(null); }}>
          <Bookmark size={15} aria-hidden="true" />
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

/** Grey placeholder rows while the first page of jobs loads. */
function SkeletonRows() {
  return (
    <div className="job-list skeleton-list" aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex flex-col gap-2 border-0 border-b border-solid border-line px-4 py-3 last:border-0">
          <div className="skeleton h-3.5" style={{ width: `${55 - (i % 3) * 10}%` }} />
          <div className="skeleton h-3 w-2/5" />
        </div>
      ))}
    </div>
  );
}
