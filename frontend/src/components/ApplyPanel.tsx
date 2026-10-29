// "Apply" on a Greenhouse job: pick a saved résumé or upload one, then a
// browser window opens the real form filled in from your profile. You check
// it and press Submit there; this panel follows along.

import { AlertTriangle, CheckCircle2, FileUp, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatDate } from "../format";
import { useLoad } from "../state";
import type { ApplyState } from "../types";

const WORKING = ["opening", "filling", "ready"];

export default function ApplyPanel({ jobId, onApplied }: { jobId: number; onApplied: () => void }) {
  const setup = useLoad(() => api.applySetup(), "apply-setup");
  const [resume, setResume] = useState("");
  const [state, setState] = useState<ApplyState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const appliedOnce = useRef(false);

  // Pick up a window that's already open (e.g. after reloading the page).
  useEffect(() => {
    api.applyState().then((s) => s.job_id === jobId && setState(s)).catch(() => undefined);
  }, [jobId]);

  // Follow the window while it's open.
  useEffect(() => {
    if (!state?.phase || !WORKING.includes(state.phase)) {
      if (state?.phase === "submitted" && !appliedOnce.current) {
        appliedOnce.current = true;
        onApplied();
      }
      return;
    }
    const timer = window.setTimeout(() => api.applyState().then(setState).catch(() => undefined), 1500);
    return () => window.clearTimeout(timer);
  }, [state, onApplied]);

  const s = setup.data;
  const saved = s?.resumes ?? [];
  useEffect(() => {
    if (!resume && saved.length) setResume(saved[0].name);
  }, [saved, resume]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      const result = await api.uploadResume(file);
      setup.setData((d) => (d ? { ...d, resumes: result.resumes } : d));
      setResume(result.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function apply() {
    setBusy(true);
    setError(null);
    appliedOnce.current = false;
    try {
      setState(await api.applyToJob(jobId, resume));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!s) return null;
  const blocked = s.browser ?? s.profile.error ??
    (s.profile.missing.length ? `Add to profile.local.toml: ${s.profile.missing.join(", ")}.` : null);
  const working = state?.phase && WORKING.includes(state.phase);

  return (
    <section className="panel apply-panel">
      <h2>Apply</h2>
      {blocked ? (
        <p className="notice">{blocked}</p>
      ) : working ? (
        <Progress state={state} />
      ) : (
        <>
          <p className="hint">
            Opens the application in a browser window, filled in from your profile. You check it and press Submit
            there.
          </p>
          <label className="stack">
            Résumé
            <select value={resume} onChange={(e) => setResume(e.target.value)} disabled={!saved.length}>
              {!saved.length && <option value="">None saved yet</option>}
              {saved.map((r) => (
                <option key={r.name} value={r.name}>
                  {r.name} ({formatDate(r.saved_at)})
                </option>
              ))}
            </select>
          </label>
          <div className="apply-actions">
            <button type="button" onClick={() => fileInput.current?.click()}>
              <FileUp size={15} aria-hidden="true" />
              Upload a résumé
            </button>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.doc,.docx"
              hidden
              onChange={(e) => upload(e.target.files?.[0])}
            />
            <button type="button" className="primary" disabled={!resume || busy} onClick={apply}>
              <Send size={15} aria-hidden="true" />
              {busy ? "Preparing…" : "Open pre-filled application"}
            </button>
          </div>
          {state?.phase && !working && <Outcome state={state} />}
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function Progress({ state }: { state: ApplyState }) {
  if (state.phase !== "ready") return <p className="task-status">{state.message}</p>;
  const todo = state.todo ?? [];
  const checks = (state.filled ?? []).filter((f) => f.check);
  return (
    <div className="apply-progress" aria-live="polite">
      <p>
        <strong>The form is open in a browser window.</strong> {state.filled?.length ?? 0} fields filled in with{" "}
        {state.resume}. Check everything, then press Submit there.
      </p>
      {todo.length > 0 && (
        <>
          <h3>For you to answer</h3>
          <ul>
            {todo.map((t) => (
              <li key={t.label}>
                {t.label}
                {t.required && <span className="tag warn">Required</span>}
                {t.why && <span className="muted small"> {t.why}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {checks.length > 0 && (
        <>
          <h3>Filled from a guess: check these</h3>
          <ul>
            {checks.map((f) => (
              <li key={f.label}>{f.label}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Outcome({ state }: { state: ApplyState }) {
  const ok = state.phase === "submitted";
  return (
    <p className={`apply-outcome${ok ? " ok" : state.phase === "error" ? " error" : ""}`} role="status">
      {ok ? <CheckCircle2 size={16} aria-hidden="true" /> : <AlertTriangle size={16} aria-hidden="true" />}
      {state.message}
    </p>
  );
}
