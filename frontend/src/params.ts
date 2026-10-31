// The jobs list keeps its filters in the URL, using the API's own parameter
// names, so a view can be bookmarked, saved as a search, or sent to export.

export function getList(params: URLSearchParams, key: string): string[] {
  return (params.get(key) ?? "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

/** A copy of *params* with *key* set (or removed when empty); paging restarts. */
export function withParam(params: URLSearchParams, key: string, value: string | string[] | null): URLSearchParams {
  const next = new URLSearchParams(params);
  const text = Array.isArray(value) ? value.join(",") : value;
  if (text) next.set(key, text);
  else next.delete(key);
  if (key !== "page") next.delete("page");
  return next;
}

export function toggleInList(params: URLSearchParams, key: string, item: string): URLSearchParams {
  const current = getList(params, key);
  const next = current.includes(item) ? current.filter((v) => v !== item) : [...current, item];
  return withParam(params, key, next);
}

export function isOn(params: URLSearchParams, key: string): boolean {
  return params.get(key) === "1";
}

/** The filters worth saving: everything except paging. */
export function savedFilters(params: URLSearchParams): Record<string, string> {
  const out: Record<string, string> = {};
  params.forEach((value, key) => {
    if (key !== "page") out[key] = value;
  });
  return out;
}

const RESULTS_KEY = "jobradar-results";

/** Remember the jobs list's search, so a job opened in a new tab can go back to it. */
export function rememberResults(params: URLSearchParams): void {
  try {
    localStorage.setItem(RESULTS_KEY, params.toString());
  } catch {
    // Storage refused (private window): "Back to results" then opens the plain list.
  }
}

/** The jobs list as last seen: "/?q=...", or "/" when there's none. */
export function lastResults(): string {
  try {
    const search = localStorage.getItem(RESULTS_KEY);
    return search ? `/?${search}` : "/";
  } catch {
    return "/";
  }
}
