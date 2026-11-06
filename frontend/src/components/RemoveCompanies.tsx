// Removing companies from the list: one confirm, then the result. The server
// saves a copy of what it removes (data/removed-companies-*.db) first, and
// keeps companies with saved or applied jobs unless you confirm those too.

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import type { RemoveResult } from "../types";

interface Props {
  companies: { id: number; name: string }[];
  /** Called after each removal, with what went. */
  onRemoved: (result: RemoveResult) => void;
  /** Called when the panel is finished with: cancelled, or nothing left to ask. */
  onClose: () => void;
}

const names = (list: { name: string }[]) =>
  list.length <= 3 ? list.map((c) => c.name).join(", ") : `${list.slice(0, 3).map((c) => c.name).join(", ")} and ${list.length - 3} more`;

export default function RemoveCompanies({ companies, onRemoved, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kept, setKept] = useState<RemoveResult["kept"] | null>(null);

  async function remove(ids: number[], includeTracked: boolean) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.removeCompanies(ids, includeTracked);
      onRemoved(result);
      if (result.kept.length) setKept(result.kept);
      else onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const one = companies.length === 1;
  return (
    <div className="remove-panel" role="alertdialog" aria-label="Remove companies">
      {kept ? (
        <>
          <p>
            <strong>
              Kept {kept.length === 1 ? kept[0].name : `${kept.length} companies`}
            </strong>{" "}
            because you've saved, applied to or written notes on{" "}
            {kept.length === 1 ? "its jobs" : "their jobs"}
            {kept.length > 1 && <> ({names(kept)})</>}. Removing{" "}
            {kept.length === 1 ? "it" : "them"} takes that tracking off the Applications page too.
          </p>
          <div className="remove-actions">
            <button type="button" className="danger" disabled={busy} onClick={() => remove(kept.map((c) => c.id), true)}>
              <Trash2 size={15} aria-hidden="true" />
              Remove {kept.length === 1 ? "it" : "them"} too
            </button>
            <button type="button" disabled={busy} onClick={onClose}>
              Keep {kept.length === 1 ? "it" : "them"}
            </button>
          </div>
        </>
      ) : (
        <>
          <p>
            <strong>Remove {one ? companies[0].name : `${companies.length} companies`}?</strong>{" "}
            {one ? "Its" : "Their"} job boards and jobs go too, and scans stop checking {one ? "it" : "them"}. A copy is
            saved in the <code>data</code> folder first.
            {!one && <span className="hint"> {names(companies)}.</span>}
          </p>
          <div className="remove-actions">
            <button type="button" className="danger" disabled={busy} onClick={() => remove(companies.map((c) => c.id), false)}>
              <Trash2 size={15} aria-hidden="true" />
              Remove {one ? "company" : `${companies.length} companies`}
            </button>
            <button type="button" disabled={busy} onClick={onClose}>
              Cancel
            </button>
          </div>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** One line saying what a removal did. */
export function removedText(result: RemoveResult): string {
  const n = result.removed.length;
  if (!n) return "";
  const what = n === 1 ? result.removed[0].name : `${n} companies`;
  const jobs = `${result.jobs.toLocaleString("en-CA")} ${result.jobs === 1 ? "job" : "jobs"}`;
  return `Removed ${what} and ${jobs}. A copy is in data/${result.archive}.`;
}
