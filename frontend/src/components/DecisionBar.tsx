// The three decisions you make about most postings, as buttons with their
// keys: Save (S), Not interested (X), Applied (A). Pressing the one that's
// already on takes it back to "Not reviewed".

import { Bookmark, CircleCheck, EyeOff } from "lucide-react";
import type { JobStatus } from "../types";

export const DECISIONS: { status: JobStatus; label: string; key: string; icon: typeof Bookmark }[] = [
  { status: "saved", label: "Save", key: "s", icon: Bookmark },
  { status: "not_interested", label: "Not interested", key: "x", icon: EyeOff },
  { status: "applied", label: "Applied", key: "a", icon: CircleCheck },
];

interface Props {
  status: JobStatus;
  busy?: boolean;
  /** Show each button's key beside its name. */
  showKeys?: boolean;
  onDecide: (status: JobStatus) => void;
}

export default function DecisionBar({ status, busy, showKeys, onDecide }: Props) {
  return (
    <div className="decision-bar" role="group" aria-label="Decide">
      {DECISIONS.map(({ status: s, label, key, icon: Icon }) => {
        const on = status === s;
        return (
          <button
            key={s}
            type="button"
            className={`decision decision-${s}${on ? " on" : ""}`}
            aria-pressed={on}
            aria-keyshortcuts={key.toUpperCase()}
            title={on ? `${label} (${key.toUpperCase()}): press again to undo` : `${label} (${key.toUpperCase()})`}
            disabled={busy}
            onClick={() => onDecide(on ? "new" : s)}
          >
            <Icon size={15} aria-hidden="true" />
            {label}
            {showKeys && <kbd aria-hidden="true">{key.toUpperCase()}</kbd>}
          </button>
        );
      })}
    </div>
  );
}
