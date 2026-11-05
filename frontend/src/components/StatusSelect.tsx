import { useState } from "react";
import { api } from "../api";
import { JOB_STATUS_LABEL } from "../format";
import type { JobStatus, JobTracking } from "../types";

const STATUSES = Object.keys(JOB_STATUS_LABEL) as JobStatus[];

interface Props {
  jobId: number;
  status: JobStatus;
  /** Saves the change itself and reports the result... */
  onChange?: (tracking: JobTracking) => void;
  /** ...or hands the choice to the caller, which saves it (with undo). */
  onPick?: (status: JobStatus) => void;
}

/** Changes a job's status right away; the colour dot shows the current one. */
export default function StatusSelect({ jobId, status, onChange, onPick }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(next: JobStatus) {
    if (onPick) {
      onPick(next);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const tracking = await api.patchJob(jobId, { status: next });
      onChange?.(tracking);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={`status-select status-${status}`}>
      <select
        value={status}
        disabled={saving}
        aria-label="Status"
        // Firefox changes a closed select's value on the arrow keys, and this
        // one saves on change: arrows would change a job's status by accident.
        // Alt+Down still opens the list.
        onKeyDown={(e) => {
          if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !e.altKey) e.preventDefault();
        }}
        onChange={(e) => change(e.target.value as JobStatus)}
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {JOB_STATUS_LABEL[s]}
          </option>
        ))}
      </select>
      {error && (
        <span className="error-inline" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
