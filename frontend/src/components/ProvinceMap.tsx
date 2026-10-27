import NumberFlow from "@number-flow/react";
import { motion } from "motion/react";
import type { CSSProperties } from "react";

// The ten provinces as a 5 x 2 grid, west to east, with the number of
// matching jobs on each. Clicking a tile filters by it. The territories
// (YT, NT, NU) are left out: they almost never have jobs, and their jobs
// still count in "all of Canada".

const TILES: { code: string; row: number; col: number }[] = [
  { code: "BC", row: 1, col: 1 },
  { code: "AB", row: 1, col: 2 },
  { code: "SK", row: 1, col: 3 },
  { code: "MB", row: 1, col: 4 },
  { code: "ON", row: 1, col: 5 },
  { code: "QC", row: 2, col: 1 },
  { code: "NB", row: 2, col: 2 },
  { code: "NS", row: 2, col: 3 },
  { code: "PE", row: 2, col: 4 },
  { code: "NL", row: 2, col: 5 },
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
            <motion.button
              key={code}
              type="button"
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.92 }}
              animate={{ scale: on ? 1.06 : 1 }}
              transition={{ type: "spring", stiffness: 500, damping: 24 }}
              className={`tile${on ? " on" : ""}${count === 0 ? " none" : ""}${weight > 0.55 ? " deep" : ""}`}
              style={{ gridRow: row, gridColumn: col, "--weight": weight } as CSSProperties}
              aria-pressed={on}
              title={`${names[code] ?? code}: ${count.toLocaleString("en-CA")} jobs`}
              onClick={() => onToggle(code)}
            >
              <span className="code">{code}</span>
              <span className="count">{counts ? <NumberFlow value={count} locales="en-CA" /> : "·"}</span>
            </motion.button>
          );
        })}
      </div>
      <motion.button
        type="button"
        whileTap={{ scale: 0.98 }}
        className={`tile remote${selected.includes(REMOTE) ? " on" : ""}`}
        aria-pressed={selected.includes(REMOTE)}
        onClick={() => onToggle(REMOTE)}
      >
        <span className="code">Remote anywhere in Canada</span>
        <span className="count">{counts ? <NumberFlow value={counts[REMOTE] ?? 0} locales="en-CA" /> : "·"}</span>
      </motion.button>
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
