// Add one job by its link: read the page, let the user check and complete
// what it says, then save. For postings on sites the app can't scan.

import { Link2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { JOB_STATUS_LABEL } from "../format";
import { useApp } from "../state";
import type { JobDraft, JobStatus } from "../types";

const STATUSES: JobStatus[] = ["saved", "applied", "interviewing", "offer", "rejected"];

export default function AddJobByLink({ onClose }: { onClose: () => void }) {
  const { meta } = useApp();
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [draft, setDraft] = useState<JobDraft | null>(null);
  const [existing, setExisting] = useState<number | null>(null);
  const [status, setStatus] = useState<JobStatus>("applied");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function read(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDraft(null);
    setExisting(null);
    try {
      const found = await api.readJobLink(url.trim());
      if (found.existing !== undefined) setExisting(found.existing);
      else if (found.draft) setDraft(found.draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const { found: _found, note: _note, country: _country, ...job } = draft;
      const saved = await api.addManualJob({ ...job, status });
      navigate(`/jobs/${saved.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  const set = (change: Partial<JobDraft>) => setDraft((d) => (d ? { ...d, ...change } : d));
  const abroad = draft && draft.country && draft.country !== "CA";
  const provinces = (meta?.provinces ?? []).filter((p) => !["YT", "NT", "NU"].includes(p.code));

  return (
    <section className="panel add-job" aria-label="Add a job by its link">
      <h2>Add a job by its link</h2>
      <p className="hint">
        For a posting the app can't scan (Taleo, iCIMS, Oracle, a job site, LinkedIn). Paste its link; the details
        are read from the page for you to check.
      </p>
      <form className="link-row" onSubmit={read}>
        <input
          type="url"
          required
          value={url}
          placeholder="https://…"
          aria-label="Link to the job posting"
          onChange={(e) => setUrl(e.target.value)}
        />
        <button type="submit" className="primary" disabled={busy || !url.trim()}>
          <Link2 size={15} aria-hidden="true" />
          {busy && !draft ? "Reading…" : "Read posting"}
        </button>
        <button type="button" className="link" onClick={onClose}>
          Cancel
        </button>
      </form>

      {existing !== null && (
        <p className="notice">
          That job is already in your list. <Link to={`/jobs/${existing}`}>Open it</Link> to change its status.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {draft && (
        <form className="draft" onSubmit={save}>
          {draft.note && <p className="notice">{draft.note}</p>}
          {abroad && (
            <p className="notice">
              The page says this job is outside Canada ({draft.country}). The app only lists Canadian jobs: pick a
              province or remote only if that's right.
            </p>
          )}
          <label className="stack">
            Title
            <input required value={draft.title} onChange={(e) => set({ title: e.target.value })} />
          </label>
          <label className="stack">
            Company
            <input
              required
              value={draft.company}
              onChange={(e) => set({ company: e.target.value, company_id: null })}
            />
            <span className="hint">
              {draft.company_id !== null
                ? "Matches a company in your list."
                : "Not in your list yet: it will be added."}
            </span>
          </label>
          <div className="draft-row">
            <label className="stack">
              City
              <input value={draft.city} onChange={(e) => set({ city: e.target.value })} />
            </label>
            <label className="stack">
              Province
              <select value={draft.province} onChange={(e) => set({ province: e.target.value })}>
                <option value="">{draft.remote ? "Anywhere in Canada" : "Pick one"}</option>
                {provinces.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={draft.remote} onChange={(e) => set({ remote: e.target.checked })} />
              Remote
            </label>
          </div>
          <label className="stack">
            Description
            <textarea rows={6} value={draft.description} onChange={(e) => set({ description: e.target.value })} />
            <span className="hint">Optional. The experience level and years asked are read from it.</span>
          </label>
          <div className="draft-row">
            <label className="stack">
              My status
              <select value={status} onChange={(e) => setStatus(e.target.value as JobStatus)}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {JOB_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Saving…" : "Save job"}
          </button>
        </form>
      )}
    </section>
  );
}
