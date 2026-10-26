import { useEffect, useState, type FormEvent } from "react";
import { JOB_STATUS_LABEL, SIZE_LABEL, SYSTEM_LABEL, WORKPLACE_LABEL } from "../format";
import { getList, isOn, toggleInList, withParam } from "../params";
import type { Meta } from "../types";
import Chips from "./Chips";
import ProvinceMap from "./ProvinceMap";

const POSTED_WITHIN = [
  { value: "", label: "Any time" },
  { value: "1", label: "Last 24 hours" },
  { value: "3", label: "Last 3 days" },
  { value: "7", label: "Last week" },
  { value: "14", label: "Last 2 weeks" },
  { value: "30", label: "Last month" },
  { value: "90", label: "Last 3 months" },
];

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
          <button type="submit">Search</button>
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
          value={params.get("posted_within") ?? ""}
          onChange={(e) => setParams(withParam(params, "posted_within", e.target.value || null))}
        >
          {POSTED_WITHIN.map((o) => (
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

      <details className="more" open={moreOpen} onToggle={(e) => setMoreOpen(e.currentTarget.open)}>
        <summary>More filters</summary>
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
      </details>

      {active && (
        <button type="button" className="link clear-all" onClick={() => setParams(new URLSearchParams())}>
          Clear all filters
        </button>
      )}
    </aside>
  );
}
