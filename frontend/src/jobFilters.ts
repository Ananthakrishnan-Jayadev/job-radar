// The jobs list's filters as things you can read and undo: the posted-date
// choices, the filters in use (each with a way to take it off), and a check
// that the address only holds filters the list understands.

import { JOB_STATUS_LABEL, LEVEL_LABEL, SIZE_LABEL, SYSTEM_LABEL, WORKPLACE_LABEL, YEARS_LABEL, formatDateTime } from "./format";
import { getList, toggleInList, withParam } from "./params";
import type { Meta } from "./types";

export const REMOTE = "REMOTE";

// "within:7" → posted_within=7; "before:30" → posted_before=30 (older than that).
export const POSTED = [
  { value: "", label: "Any time" },
  { value: "within:1", label: "Last 24 hours" },
  { value: "within:3", label: "Last 3 days" },
  { value: "within:7", label: "Less than a week ago" },
  { value: "within:14", label: "Last 2 weeks" },
  { value: "within:30", label: "Less than a month ago" },
  { value: "within:90", label: "Last 3 months" },
  { value: "before:30", label: "More than a month ago" },
];

export function postedValue(params: URLSearchParams): string {
  if (params.get("posted_within")) return `within:${params.get("posted_within")}`;
  if (params.get("posted_before")) return `before:${params.get("posted_before")}`;
  return "";
}

export function withPosted(params: URLSearchParams, value: string): URLSearchParams {
  const [kind, days] = value.split(":");
  const cleared = withParam(withParam(params, "posted_within", null), "posted_before", null);
  return kind ? withParam(cleared, `posted_${kind}`, days) : cleared;
}

export interface ActiveFilter {
  key: string;
  label: string;
  /** The same search without this filter. */
  remove: () => URLSearchParams;
}

const FLAGS: Record<string, string> = {
  title_only: "Titles only",
  all_roles: "All roles",
  has_salary: "Salary listed",
  include_closed: "Closed included",
  include_ignored: "Ignored companies included",
};

// Filters that take several values ("ON,BC"), with how each value reads.
function listFilters(meta: Meta): [string, (v: string) => string][] {
  const province = Object.fromEntries(meta.provinces.map((p) => [p.code, p.name]));
  const role = Object.fromEntries(meta.role_categories.map((r) => [r.name, r.label]));
  return [
    ["provinces", (v) => (v === REMOTE ? "Remote in Canada" : province[v] ?? v)],
    ["roles", (v) => role[v] ?? v],
    ["levels", (v) => LEVEL_LABEL[v] ?? v],
    ["years", (v) => YEARS_LABEL[v] ?? v],
    ["sizes", (v) => `${SIZE_LABEL[v] ?? v} employees`],
    ["status", (v) => JOB_STATUS_LABEL[v as keyof typeof JOB_STATUS_LABEL] ?? v],
    ["workplaces", (v) => WORKPLACE_LABEL[v as keyof typeof WORKPLACE_LABEL] ?? v],
    ["systems", (v) => SYSTEM_LABEL[v] ?? v],
  ];
}

/** Every filter in use, in words. */
export function activeFilters(meta: Meta, params: URLSearchParams, companyName?: string): ActiveFilter[] {
  const active: ActiveFilter[] = [];
  const query = params.get("q");
  if (query) active.push({ key: "q", label: `“${query}”`, remove: () => withParam(params, "q", null) });

  for (const [key, label] of listFilters(meta)) {
    for (const value of getList(params, key)) {
      active.push({ key: `${key}:${value}`, label: label(value), remove: () => toggleInList(params, key, value) });
    }
  }

  const posted = POSTED.find((o) => o.value && o.value === postedValue(params));
  if (posted) {
    active.push({ key: "posted", label: `Posted ${posted.label.toLowerCase()}`, remove: () => withPosted(params, "") });
  }
  if (params.has("new_since")) {
    // From the "new since my last visit" box, or from a scan's "Show them".
    const since = params.get("new_since") ?? "";
    active.push({
      key: "new_since",
      label: `Found since ${formatDateTime(since)}`,
      remove: () => withParam(params, "new_since", null),
    });
  }
  if (params.has("company")) {
    active.push({ key: "company", label: companyName ?? "One company", remove: () => withParam(params, "company", null) });
  }
  for (const [key, label] of Object.entries(FLAGS)) {
    if (params.get(key) === "1") active.push({ key, label, remove: () => withParam(params, key, null) });
  }
  return active;
}

/** Every filter off; the sort order stays. */
export function withSortOnly(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams();
  for (const key of ["sort", "order"]) {
    const value = params.get(key);
    if (value) next.set(key, value);
  }
  return next;
}

/**
 * The address as the list understands it. A filter named twice
 * (`levels=entry&levels=mid`, from an old or hand-made link) would show one
 * value while the server used the other: several values are merged, and a
 * single setting keeps the last one, as the server does. Values the list
 * doesn't know ("junior") are dropped, and province codes are upper-cased.
 */
export function normalizeParams(meta: Meta, params: URLSearchParams): URLSearchParams {
  const known: Record<string, string[]> = {
    provinces: [...meta.provinces.map((p) => p.code), REMOTE],
    roles: meta.role_categories.map((r) => r.name),
    levels: meta.levels,
    years: meta.year_bands,
    sizes: meta.size_bands,
    status: meta.job_statuses,
    workplaces: meta.workplaces,
    systems: meta.systems,
  };
  const next = new URLSearchParams();
  for (const key of new Set(params.keys())) {
    const values = params.getAll(key);
    if (key in known) {
      const allowed = known[key];
      const merged = values
        .flatMap((v) => v.split(","))
        .map((v) => v.trim())
        .map((v) => (key === "provinces" ? v.toUpperCase() : v))
        .filter((v, i, all) => v && allowed.includes(v) && all.indexOf(v) === i);
      if (merged.length) next.set(key, merged.join(","));
    } else {
      next.set(key, values[values.length - 1]);
    }
  }
  return next;
}
