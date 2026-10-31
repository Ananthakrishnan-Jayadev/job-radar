// What the jobs list is filtered by, as a row of chips above the results:
// each one says a filter in words and takes it off with one click.

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { JOB_STATUS_LABEL, LEVEL_LABEL, SIZE_LABEL, SYSTEM_LABEL, WORKPLACE_LABEL, YEARS_LABEL } from "../format";
import { getList, toggleInList, withParam } from "../params";
import type { Meta } from "../types";
import { POSTED, postedValue, withPosted } from "./JobFilters";
import { REMOTE } from "./ProvinceMap";

interface Props {
  meta: Meta;
  params: URLSearchParams;
  setParams: (next: URLSearchParams) => void;
  /** The company's name when the list is narrowed to one company. */
  companyName?: string;
}

interface Active {
  key: string;
  label: string;
  remove: () => URLSearchParams;
}

const FLAGS: Record<string, string> = {
  title_only: "Titles only",
  all_roles: "All roles",
  has_salary: "Salary listed",
  include_closed: "Closed included",
  include_ignored: "Ignored companies included",
};

export default function ActiveFilters({ meta, params, setParams, companyName }: Props) {
  const province = Object.fromEntries(meta.provinces.map((p) => [p.code, p.name]));
  const role = Object.fromEntries(meta.role_categories.map((r) => [r.name, r.label]));
  const active: Active[] = [];

  const query = params.get("q");
  if (query) active.push({ key: "q", label: `“${query}”`, remove: () => withParam(params, "q", null) });

  const lists: [string, (v: string) => string][] = [
    ["provinces", (v) => (v === REMOTE ? "Remote in Canada" : province[v] ?? v)],
    ["roles", (v) => role[v] ?? v],
    ["levels", (v) => LEVEL_LABEL[v] ?? v],
    ["years", (v) => YEARS_LABEL[v] ?? v],
    ["sizes", (v) => `${SIZE_LABEL[v] ?? v} employees`],
    ["status", (v) => JOB_STATUS_LABEL[v as keyof typeof JOB_STATUS_LABEL] ?? v],
    ["workplaces", (v) => WORKPLACE_LABEL[v as keyof typeof WORKPLACE_LABEL] ?? v],
    ["systems", (v) => SYSTEM_LABEL[v] ?? v],
  ];
  for (const [key, label] of lists) {
    for (const value of getList(params, key)) {
      active.push({ key: `${key}:${value}`, label: label(value), remove: () => toggleInList(params, key, value) });
    }
  }

  const posted = POSTED.find((o) => o.value && o.value === postedValue(params));
  if (posted) active.push({ key: "posted", label: `Posted ${posted.label.toLowerCase()}`, remove: () => withPosted(params, "") });
  if (params.has("new_since")) {
    active.push({ key: "new_since", label: "New since my last visit", remove: () => withParam(params, "new_since", null) });
  }
  if (params.has("company")) {
    active.push({ key: "company", label: companyName ?? "One company", remove: () => withParam(params, "company", null) });
  }
  for (const [key, label] of Object.entries(FLAGS)) {
    if (params.get(key) === "1") active.push({ key, label, remove: () => withParam(params, key, null) });
  }

  if (!active.length) return null;
  return (
    <div className="active-filters" aria-label="Filters in use">
      <AnimatePresence initial={false}>
        {active.map((a) => (
          <motion.button
            key={a.key}
            layout
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            type="button"
            className="active-filter"
            title={`Remove: ${a.label}`}
            onClick={() => setParams(a.remove())}
          >
            {a.label}
            <X size={13} aria-label="remove" />
          </motion.button>
        ))}
      </AnimatePresence>
      {active.length > 1 && (
        <button type="button" className="link" onClick={() => setParams(withSortOnly(params))}>
          Clear all
        </button>
      )}
    </div>
  );
}

/** Every filter off; the sort order stays. */
function withSortOnly(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams();
  for (const key of ["sort", "order"]) {
    const value = params.get(key);
    if (value) next.set(key, value);
  }
  return next;
}
