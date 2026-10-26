import type { CSSProperties } from "react";

// Canada as a grid of tiles, placed roughly where each province sits,
// with the number of matching jobs on each. Clicking a tile filters by it.

const TILES: { code: string; row: number; col: number }[] = [
  { code: "YT", row: 1, col: 1 },
  { code: "NT", row: 1, col: 2 },
  { code: "NU", row: 1, col: 3 },
  { code: "NL", row: 1, col: 7 },
  { code: "BC", row: 2, col: 1 },
  { code: "AB", row: 2, col: 2 },
  { code: "SK", row: 2, col: 3 },
  { code: "MB", row: 2, col: 4 },
  { code: "ON", row: 2, col: 5 },
  { code: "QC", row: 2, col: 6 },
  { code: "PE", row: 2, col: 7 },
  { code: "NB", row: 3, col: 6 },
  { code: "NS", row: 3, col: 7 },
];

export const REMOTE = "REMOTE";

interface Props {
  names: Record<string, string>;
  selected: string[];
  counts: Record<string, number> | undefined;
  onToggle: (code: string) => void;
  onClear: () => void;
}

export default function ProvinceMap({ names, selected, counts, onToggle, onClear }: Props) {
  const max = Math.max(1, ...TILES.map((t) => counts?.[t.code] ?? 0));
  return (
    <fieldset className="province-map">
      <legend>Where</legend>
      <div className="tiles">
        {TILES.map(({ code, row, col }) => {
          const count = counts?.[code] ?? 0;
          const on = selected.includes(code);
          // Tile shade follows its share of jobs, so busy provinces stand out.
          const weight = count === 0 ? 0 : 0.15 + 0.85 * Math.sqrt(count / max);
          return (
            <button
              key={code}
              type="button"
              className={`tile${on ? " on" : ""}${count === 0 ? " none" : ""}`}
              style={{ gridRow: row, gridColumn: col, "--weight": weight } as CSSProperties}
              aria-pressed={on}
              title={`${names[code] ?? code}: ${count.toLocaleString("en-CA")} jobs`}
              onClick={() => onToggle(code)}
            >
              <span className="code">{code}</span>
              <span className="count">{counts ? count.toLocaleString("en-CA") : "·"}</span>
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className={`tile remote${selected.includes(REMOTE) ? " on" : ""}`}
        aria-pressed={selected.includes(REMOTE)}
        onClick={() => onToggle(REMOTE)}
      >
        <span className="code">Remote anywhere in Canada</span>
        <span className="count">{counts ? (counts[REMOTE] ?? 0).toLocaleString("en-CA") : "·"}</span>
      </button>
      <p className="hint">
        {selected.length === 0 ? (
          "Showing all of Canada."
        ) : (
          <>
            Showing {selected.map((c) => (c === REMOTE ? "remote" : c)).join(", ")}.{" "}
            <button type="button" className="link" onClick={onClear}>
              Show all of Canada
            </button>
          </>
        )}
      </p>
    </fieldset>
  );
}
