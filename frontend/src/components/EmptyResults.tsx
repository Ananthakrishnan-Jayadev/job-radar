// "0 jobs", but useful: which filter is emptying the list, and how many jobs
// taking each one off would bring back.

import { useEffect, useState } from "react";
import { api } from "../api";
import { activeFilters, withSortOnly, type ActiveFilter } from "../jobFilters";
import { withParam } from "../params";
import type { Meta } from "../types";

interface Props {
  meta: Meta;
  params: URLSearchParams;
  setParams: (next: URLSearchParams) => void;
}

type Option = { filter: ActiveFilter; total: number };

export default function EmptyResults({ meta, params, setParams }: Props) {
  const active = activeFilters(meta, params);
  const [options, setOptions] = useState<Option[] | null>(null);
  const key = params.toString();

  useEffect(() => {
    let cancelled = false;
    setOptions(null);
    if (!active.length) return;
    // One count per filter in use, each with that filter taken off.
    Promise.all(
      active.map((filter) =>
        api
          .jobs(withParam(filter.remove(), "page_size", "1"))
          .then((page) => ({ filter, total: page.total }))
          .catch(() => ({ filter, total: 0 })),
      ),
    ).then((found) => {
      if (!cancelled) setOptions(found.filter((o) => o.total > 0).sort((a, b) => b.total - a.total));
    });
    return () => {
      cancelled = true;
    };
  }, [key]); // recount only when the search changes

  if (meta.open_jobs === 0) {
    return (
      <div className="empty">
        <p>No jobs yet. Run a scan to fetch jobs from the companies on your list.</p>
      </div>
    );
  }
  if (!active.length) {
    return (
      <div className="empty">
        <p>No open jobs right now.</p>
      </div>
    );
  }
  return (
    <div className="empty">
      <p>No job matches all of these filters together.</p>
      {options === null && <p className="hint">Checking which filter is doing it…</p>}
      {options && options.length > 0 && (
        <>
          <p className="hint">Taking one off would bring back:</p>
          <ul className="unblock">
            {options.map(({ filter, total }) => (
              <li key={filter.key}>
                <button type="button" onClick={() => setParams(filter.remove())}>
                  Remove {filter.label}
                  <span className="muted">
                    {total.toLocaleString("en-CA")} {total === 1 ? "job" : "jobs"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {options && options.length === 0 && (
        <p className="hint">
          Taking off any single filter still leaves nothing.{" "}
          <button type="button" className="link" onClick={() => setParams(withSortOnly(params))}>
            Clear all filters
          </button>
        </p>
      )}
    </div>
  );
}
