// A single-series column chart: HTML bars so labels stay crisp at any width.
// One series, so no legend (the heading names it); a recessive grid with
// three lines; each column shows its tip on hover or keyboard focus.

import { useState } from "react";

export interface Bar {
  key: string;
  value: number;
  /** Under the column; "" leaves it blank to avoid crowding. */
  label: string;
  /** Spoken and shown on hover: "Week of Oct 5: 2 applications". */
  tip: string;
}

/** A round top for the axis: 2, 4, 10, 20, 50, 100... at or above *most*. */
function niceTop(most: number): number {
  if (most <= 2) return 2;
  const step = 10 ** Math.floor(Math.log10(most));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * step >= most && Number.isInteger((m * step) / 2)) return m * step;
  }
  return 10 * step;
}

export default function BarChart({ bars, className = "" }: { bars: Bar[]; className?: string }) {
  const [active, setActive] = useState<number | null>(null);
  const top = niceTop(Math.max(0, ...bars.map((b) => b.value)));
  const columns = { gridTemplateColumns: `repeat(${bars.length}, 1fr)` };

  return (
    <div className={`bar-chart ${className}`}>
      <div className="plot" onMouseLeave={() => setActive(null)}>
        {[top, top / 2, 0].map((v) => (
          <div key={v} className="gridline" style={{ bottom: `${(100 * v) / top}%` }}>
            <span>{v.toLocaleString("en-CA")}</span>
          </div>
        ))}
        <div className="cols" style={columns}>
          {bars.map((b, i) => (
            <div
              key={b.key}
              className={`col${active === i ? " on" : ""}`}
              tabIndex={0}
              aria-label={b.tip}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            >
              {b.value > 0 && <span className="bar" style={{ height: `${(100 * b.value) / top}%` }} />}
              {active === i && (
                <span className={`chart-tip${i > bars.length * 0.75 ? " to-left" : i < bars.length * 0.25 ? " to-right" : ""}`} role="tooltip">
                  {b.tip}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="x-labels" style={columns} aria-hidden="true">
        {bars.map((b) => (
          <span key={b.key}>{b.label}</span>
        ))}
      </div>
    </div>
  );
}
