// Every Jobs page key in one place, opened with "?". Esc, "?" again or a
// click outside closes it.

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

const KEYS: [string[], string][] = [
  [["J"], "Next job (on to the next page at the end)"],
  [["K"], "Previous job"],
  [["S"], "Save"],
  [["X"], "Not interested"],
  [["A"], "Applied"],
  [["U"], "Undo the last decision"],
  [["O"], "Open the job's full page"],
  [["T", "Space"], "Tick or untick the job"],
  [["Shift", "click"], "Tick every job from the last one ticked"],
  [["Esc"], "Untick all"],
  [["/"], "Search"],
  [["?"], "This list"],
];

export default function KeyHelp({ onClose }: { onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.focus();
  }, []);

  return (
    <div className="key-help-backdrop" onClick={onClose}>
      <div
        ref={box}
        className="key-help"
        role="dialog"
        aria-modal="true"
        aria-labelledby="key-help-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="key-help-head">
          <h2 id="key-help-title">Keys on the Jobs page</h2>
          <button type="button" className="quiet" aria-label="Close" onClick={onClose}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <dl>
          {KEYS.map(([keys, what]) => (
            <div key={what}>
              <dt>
                {keys.map((k) => (
                  <kbd key={k}>{k}</kbd>
                ))}
              </dt>
              <dd>{what}</dd>
            </div>
          ))}
        </dl>
        <p className="hint">
          With jobs ticked, S, X and A decide all of them. A job posted for several places is decided everywhere at
          once.
        </p>
      </div>
    </div>
  );
}
