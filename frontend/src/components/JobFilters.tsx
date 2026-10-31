import { ChevronDown, Search, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { JOB_STATUS_LABEL, LEVEL_LABEL, SIZE_LABEL, SYSTEM_LABEL, WORKPLACE_LABEL, YEARS_LABEL } from "../format";
import { getList, isOn, toggleInList, withParam } from "../params";
import { useApp } from "../state";
import type { Meta } from "../types";
import Chips from "./Chips";
import ProvinceMap from "./ProvinceMap";
import TaskStatus from "./TaskStatus";

// "within:7" → posted_within=7; "before:30" → posted_before=30 (older than that).
const POSTED = [
  { value: "", label: "Any time" },
  { value: "within:1", label: "Last 24 hours" },
  { value: "within:3", label: "Last 3 days" },
  { value: "within:7", label: "Less than a week ago" },
  { value: "within:14", label: "Last 2 weeks" },
  { value: "within:30", label: "Less than a month ago" },
  { value: "within:90", label: "Last 3 months" },
  { value: "before:30", label: "More than a month ago" },
];

function postedValue(params: URLSearchParams): string {
  if (params.get("posted_within")) return `within:${params.get("posted_within")}`;
  if (params.get("posted_before")) return `before:${params.get("posted_before")}`;
  return "";
}

function withPosted(params: URLSearchParams, value: string): URLSearchParams {
  const [kind, days] = value.split(":");
  const cleared = withParam(withParam(params, "posted_within", null), "posted_before", null);
  return kind ? withParam(cleared, `posted_${kind}`, days) : cleared;
}

interface Props {
  meta: Meta;
  params: URLSearchParams;
  setParams: (next: URLSearchParams) => void;
  provinceCounts: Record<string, number> | undefined;
  previousVisit: string | null;
}

export default function JobFilters({ meta, params, setParams, provinceCounts, previousVisit }: Props) {
  const [query, setQuery] = useState(params.get("q") ?? "");
  // Remember whether "More filters" is open; start open if one of its filters is on.
  const [moreOpen, setMoreOpen] = useState(
    () => params.has("systems") || ["has_salary", "include_closed", "include_ignored"].some((k) => isOn(params, k)),
  );
  useEffect(() => setQuery(params.get("q") ?? ""), [params]);

  const names = Object.fromEntries(meta.provinces.map((p) => [p.code, p.name]));
  const flag = (key: string) => (on: boolean) => setParams(withParam(params, key, on ? "1" : null));

  function search(event: FormEvent) {
    event.preventDefault();
    setParams(withParam(params, "q", query.trim() || null));
  }

  const active = [...params.keys()].some((k) => k !== "page" && k !== "sort" && k !== "order");

  return (
    <aside className="filters" aria-label="Filters">
      <form className="search" onSubmit={search} role="search">
        <label htmlFor="q">Search jobs</label>
        <div className="search-row">
          <input
            id="q"
            type="search"
            value={query}
            placeholder='ai engineer, "data analyst", python'
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" aria-label="Search" title="Search">
            <Search size={16} aria-hidden="true" />
          </button>
        </div>
        <label className="check">
          <input type="checkbox" checked={isOn(params, "title_only")} onChange={(e) => flag("title_only")(e.target.checked)} />
          Titles only
        </label>
        <p className="hint">Use quotes for exact phrases, OR for either word, and * to match word starts (analy*).</p>
      </form>

      <ProvinceMap
        names={names}
        selected={getList(params, "provinces")}
        counts={provinceCounts}
        onToggle={(code) => setParams(toggleInList(params, "provinces", code))}
        onClear={() => setParams(withParam(params, "provinces", null))}
      />

      <fieldset className="field">
        <legend>Posted</legend>
        <select
          value={postedValue(params)}
          onChange={(e) => setParams(withPosted(params, e.target.value))}
        >
          {POSTED.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {previousVisit && (
          <label className="check">
            <input
              type="checkbox"
              checked={params.has("new_since")}
              onChange={(e) => setParams(withParam(params, "new_since", e.target.checked ? previousVisit : null))}
            />
            Only new since my last visit
          </label>
        )}
      </fieldset>

      {meta.role_categories.length > 0 && (
        <fieldset className="field">
          <Chips
            legend="Role"
            options={meta.role_categories.map((r) => ({ value: r.name, label: r.label }))}
            selected={getList(params, "roles")}
            onToggle={(v) => setParams(toggleInList(params, "roles", v))}
          />
          {!params.has("roles") && (
            <label className="check">
              <input type="checkbox" checked={isOn(params, "all_roles")} onChange={(e) => flag("all_roles")(e.target.checked)} />
              Show all roles, not just {meta.role_categories.filter((r) => r.enabled).map((r) => r.name).join(", ")}
            </label>
          )}
        </fieldset>
      )}

      <LevelFilter meta={meta} params={params} setParams={setParams} />

      <Chips
        legend="Company size"
        options={meta.size_bands.map((b) => ({ value: b, label: SIZE_LABEL[b] ?? b }))}
        selected={getList(params, "sizes")}
        onToggle={(v) => setParams(toggleInList(params, "sizes", v))}
      />

      <Chips
        legend="My status"
        options={meta.job_statuses.map((s) => ({ value: s, label: JOB_STATUS_LABEL[s] }))}
        selected={getList(params, "status")}
        onToggle={(v) => setParams(toggleInList(params, "status", v))}
      />

      <Chips
        legend="Workplace"
        options={meta.workplaces.map((w) => ({ value: w, label: WORKPLACE_LABEL[w] }))}
        selected={getList(params, "workplaces")}
        onToggle={(v) => setParams(toggleInList(params, "workplaces", v))}
      />

      <div className="more">
        <button
          type="button"
          className="more-toggle"
          aria-expanded={moreOpen}
          aria-controls="more-filters"
          onClick={() => setMoreOpen((open) => !open)}
        >
          More filters
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        <AnimatePresence initial={false}>
          {moreOpen && (
            <motion.div
              id="more-filters"
              className="more-body"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.3, 0, 0.2, 1] }}
            >
              <div>
                <Chips
                  legend="Job system"
                  options={meta.systems_in_use.map((s) => ({ value: s, label: SYSTEM_LABEL[s] ?? s }))}
                  selected={getList(params, "systems")}
                  onToggle={(v) => setParams(toggleInList(params, "systems", v))}
                />
                <label className="check">
                  <input type="checkbox" checked={isOn(params, "has_salary")} onChange={(e) => flag("has_salary")(e.target.checked)} />
                  Salary listed
                </label>
                <label className="check">
                  <input type="checkbox" checked={isOn(params, "include_closed")} onChange={(e) => flag("include_closed")(e.target.checked)} />
                  Include closed postings
                </label>
                <label className="check">
                  <input type="checkbox" checked={isOn(params, "include_ignored")} onChange={(e) => flag("include_ignored")(e.target.checked)} />
                  Include ignored companies
                </label>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {active && (
        <button type="button" className="link clear-all" onClick={() => setParams(new URLSearchParams())}>
          Clear all filters
        </button>
      )}
    </aside>
  );
}

/** Experience level chips, and asking the AI model about jobs the rules couldn't place. */
function LevelFilter({ meta, params, setParams }: Pick<Props, "meta" | "params" | "setParams">) {
  const { task, watchTask } = useApp();
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    setError(null);
    try {
      watchTask(await api.askLevels());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <fieldset className="field">
      <Chips
        legend="Experience"
        options={meta.levels.map((l) => ({ value: l, label: LEVEL_LABEL[l] ?? l }))}
        selected={getList(params, "levels")}
        onToggle={(v) => setParams(toggleInList(params, "levels", v))}
      />
      <Chips
        legend="Years of experience asked"
        options={meta.year_bands.map((y) => ({ value: y, label: YEARS_LABEL[y] ?? y }))}
        selected={getList(params, "years")}
        onToggle={(v) => setParams(toggleInList(params, "years", v))}
      />
      {meta.levels_to_ask > 0 && !(task?.running && task.name === "levels") && (
        <div className="ask-ai">
          <p className="hint">
            The rules found no level or no years of experience in {meta.levels_to_ask}{" "}
            {meta.levels_to_ask === 1 ? "job" : "jobs"}. The AI model can read those postings once.
          </p>
          <button type="button" disabled={task?.running} onClick={ask}>
            <Sparkles size={15} aria-hidden="true" />
            Ask {meta.ollama_model}
          </button>
        </div>
      )}
      <TaskStatus name="levels" />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
