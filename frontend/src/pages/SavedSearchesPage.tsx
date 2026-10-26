import { Link } from "react-router-dom";
import { api } from "../api";
import { useLoad } from "../state";
import type { SavedSearch } from "../types";

const FILTER_LABEL: Record<string, string> = {
  title_only: "titles only",
  provinces: "where",
  sizes: "size",
  status: "status",
  posted_within: "posted within (days)",
  workplaces: "workplace",
  systems: "job system",
  has_salary: "salary listed",
  include_closed: "closed included",
  include_ignored: "ignored companies included",
  company: "company",
  sort: "sorted by",
  roles: "role",
  all_roles: "all roles",
};

function describe(search: SavedSearch): string {
  const parts = Object.entries(search.filters)
    .filter(([key]) => key !== "q" && key !== "order" && key !== "new_since")
    .map(([key, value]) => (value === "1" ? FILTER_LABEL[key] ?? key : `${FILTER_LABEL[key] ?? key}: ${value}`));
  return parts.length ? parts.join("; ") : "No other filters";
}

export default function SavedSearchesPage() {
  const searches = useLoad(() => api.savedSearches(), "all");

  async function toggleSources(search: SavedSearch) {
    const updated = await api.patchSavedSearch(search.id, { use_for_sources: !search.use_for_sources });
    searches.setData((list) => list?.map((s) => (s.id === updated.id ? updated : s)));
  }

  async function remove(search: SavedSearch) {
    if (!window.confirm(`Delete the saved search "${search.name}"?`)) return;
    await api.deleteSavedSearch(search.id);
    searches.setData((list) => list?.filter((s) => s.id !== search.id));
  }

  return (
    <div className="narrow">
      <h1>Saved searches</h1>
      <p className="lead">
        Save a search from the jobs list to come back to it in one click. Searches you mark for big job boards are
        also what large Workday sites (TD, RBC, BMO, CIBC) get searched for during a scan, since those sites have
        too many jobs to read in full.
      </p>
      {searches.error && <p className="error" role="alert">{searches.error}</p>}
      {searches.data && searches.data.length === 0 && (
        <p className="empty">
          No saved searches yet. Search for something on the <Link to="/">jobs list</Link>, then choose Save search.
        </p>
      )}
      <ul className="saved-list">
        {searches.data?.map((s) => {
          const query = new URLSearchParams(s.filters);
          if (s.query && !query.has("q")) query.set("q", s.query);
          return (
            <li key={s.id} className="panel">
              <div className="saved-head">
                <Link to={`/?${query}`} className="job-title">
                  {s.name}
                </Link>
                <button type="button" className="link danger" onClick={() => remove(s)}>
                  Delete
                </button>
              </div>
              <p>{s.query ? <q>{s.query}</q> : <span className="hint">No keywords</span>}</p>
              <p className="hint">{describe(s)}</p>
              <label className="check">
                <input type="checkbox" checked={s.use_for_sources} onChange={() => toggleSources(s)} />
                Use these keywords when scanning big job boards
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
