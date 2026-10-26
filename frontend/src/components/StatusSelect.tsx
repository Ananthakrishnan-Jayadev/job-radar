import { useState } from "react";
import { api } from "../api";
import { JOB_STATUS_LABEL } from "../format";
import type { JobStatus, JobTracking } from "../types";

const STATUSES = Object.keys(JOB_STATUS_LABEL) as JobStatus[];

interface Props {
  jobId: number;
  status: JobStatus;
  onChange: (tracking: JobTracking) => void;
}

/** Changes a job's status right away; the colour dot shows the current one. */
export default function StatusSelect({ jobId, status, onChange }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(next: JobStatus) {
    setSaving(true);
    setError(null);
    try {
      onChange(await api.patchJob(jobId, { status: next }));
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
