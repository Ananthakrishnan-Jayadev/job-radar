// A table column head you click to sort by that column. The first click
// sorts the column's natural way (names A to Z, counts highest first); a
// second click reverses it. The sort is remembered in this browser.

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useState, type ReactNode } from "react";

export type Dir = "asc" | "desc";
export type Sort<K extends string> = { key: K; dir: Dir };

/** The current sort, saved under *storageKey*; falls back to *initial*. */
export function useSort<K extends string>(storageKey: string, initial: Sort<K>, keys: readonly K[]) {
  const [sort, setSort] = useState<Sort<K>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null");
      if (saved && keys.includes(saved.key) && (saved.dir === "asc" || saved.dir === "desc")) return saved;
    } catch {
      // Unreadable or refused storage: start from the default.
    }
    return initial;
  });

  /** Sort by *key*: its first direction, or the other one if it's already the sort. */
  function sortBy(key: K, first: Dir) {
    const next: Sort<K> = sort.key === key ? { key, dir: sort.dir === "asc" ? "desc" : "asc" } : { key, dir: first };
    setSort(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      // Storage refused: it still sorts for this visit.
    }
  }
  return [sort, sortBy] as const;
}

interface Props<K extends string> {
  sortKey: K;
  sort: Sort<K>;
  /** The direction of the first click: "asc" for names, "desc" for counts. */
  first: Dir;
  onSort: (key: K, first: Dir) => void;
  className?: string;
  title?: string;
  children: ReactNode;
}

export default function SortHeader<K extends string>({ sortKey, sort, first, onSort, className, title, children }: Props<K>) {
  const on = sort.key === sortKey;
  const Icon = !on ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      className={`sortable${on ? " sorted" : ""}${className ? ` ${className}` : ""}`}
      aria-sort={on ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
      title={title}
    >
      <button type="button" onClick={() => onSort(sortKey, first)}>
        {children}
        <Icon size={13} strokeWidth={2.4} aria-hidden="true" />
      </button>
    </th>
  );
}
