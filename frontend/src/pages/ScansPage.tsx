import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { SYSTEM_LABEL, boardLabel, duration, formatCount, formatDate, formatDateTime } from "../format";
import { useApp, useLoad } from "../state";
import type { ScanRecord } from "../types";

export default function ScansPage() {
  const { scan, startScan, scanError, dataVersion } = useApp();
  const history = useLoad(() => api.scans(), `${dataVersion}|${scan?.running}`);
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <div className="narrow wide">
      <h1>Scans</h1>
      <p className="lead">
        A scan reads every enabled job board and keeps the jobs located in Canada. Jobs that disappear from their
        board are marked closed, and your statuses and notes are kept. A full scan takes several minutes, mostly for
        the large Workday sites.
      </p>

      <section className="panel scan-now">
        {scan?.running ? (
          <>
            <h2>Scanning {scan.company ?? "all companies"}</h2>
            <progress max={scan.boards_total || 1} value={scan.boards_done} />
            <p>
              {scan.boards_done} of {scan.boards_total} boards done. {formatCount(scan.jobs_new)} new jobs so far
              {scan.boards_failed > 0 && `, ${scan.boards_failed} boards failed`}.
            </p>
            <ul className="recent">
              {scan.recent.map((r, i) => (
                <li key={i} className={r.ok ? "" : "error"}>
                  {r.company} ({SYSTEM_LABEL[r.system] ?? r.system}):{" "}
                  {r.ok ? `${formatCount(r.jobs_canada)} in Canada, ${formatCount(r.jobs_new)} new` : r.error}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <h2>Scan all companies</h2>
            {scan?.error && <p className="error">The last scan stopped: {scan.error}</p>}
            {scanError && <p className="error">{scanError}</p>}
            <button type="button" className="primary" onClick={() => startScan()}>
              Scan now
            </button>
          </>
        )}
      </section>

      <BoardHealth version={`${dataVersion}|${scan?.running}`} />
      <Backups />

      <h2>Past scans</h2>
      {history.data && history.data.length === 0 && <p className="empty">No scans yet.</p>}
      {history.data && history.data.length > 0 && (
        <table className="scans">
          <thead>
            <tr>
              <th scope="col">Started</th>
              <th scope="col">Took</th>
              <th scope="col" className="num">Boards ok</th>
              <th scope="col" className="num">Failed</th>
              <th scope="col" className="num">New jobs</th>
              <th scope="col" className="num">Closed</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {history.data.map((s) => (
              <ScanRow key={s.id} scan={s} open={openId === s.id} onToggle={() => setOpenId(openId === s.id ? null : s.id)} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ScanRow({ scan, open, onToggle }: { scan: ScanRecord; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className={scan.boards_failed ? "has-errors" : ""}>
        <td className="nowrap">{formatDateTime(scan.started_at)}</td>
        <td className="nowrap">{scan.finished_at ? duration(scan.started_at, scan.finished_at) : "Running or stopped"}</td>
        <td className="num">{scan.boards_ok}</td>
        <td className="num">{scan.boards_failed}</td>
        <td className="num">{formatCount(scan.jobs_new)}</td>
        <td className="num">{formatCount(scan.jobs_closed)}</td>
        <td>
          <button type="button" className="link" aria-expanded={open} onClick={onToggle}>
            {open ? "Hide boards" : "Show boards"}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="detail-row">
          <td colSpan={7}>
            <ScanDetail id={scan.id} />
          </td>
        </tr>
      )}
    </>
  );
}

function ScanDetail({ id }: { id: number }) {
  const detail = useLoad(() => api.scan(id), String(id));
  if (detail.error) return <p className="error">{detail.error}</p>;
  if (!detail.data) return <p className="loading">Loading…</p>;
  return (
    <table className="scan-results">
      <tbody>
        {detail.data.results.map((r) => (
          <tr key={r.id} className={r.ok ? "" : "error"}>
            <td>
              <Link to={`/companies/${r.company_id}`}>{r.company}</Link>
            </td>
            <td>{SYSTEM_LABEL[r.system] ?? r.system}</td>
            <td className="num">{r.ok ? `${formatCount(r.jobs_canada)} of ${formatCount(r.jobs_seen)} in Canada` : "Failed"}</td>
            <td className="small">{r.error ?? ""}</td>
            <td className="num nowrap">{r.ms !== null ? `${(r.ms / 1000).toFixed(1)}s` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Boards that failed their last few scans: switch one off, or fix it on its company page. */
function BoardHealth({ version }: { version: string }) {
  const failing = useLoad(() => api.failingBoards(), version);
  const [error, setError] = useState<string | null>(null);
  if (!failing.data || failing.data.boards.length === 0) return null;

  async function switchOff(id: number) {
    setError(null);
    try {
      await api.patchBoard(id, { enabled: false });
      failing.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <section className="panel board-health">
      <h2>Boards that keep failing</h2>
      <p className="hint">
        These failed their last {failing.data.after} scans or more. The company may have moved to another job system:
        open it to add the new board, or switch this one off.
      </p>
      {error && <p className="error">{error}</p>}
      <table className="boards">
        <tbody>
          {failing.data.boards.map((b) => (
            <tr key={b.id}>
              <td>
                <Link to={`/companies/${b.company_id}`}>{b.company}</Link>
                <div className="small muted">{boardLabel(b.system, b.slug_or_url)}</div>
              </td>
              <td className="small">
                <span className="error">{b.failures} in a row</span>
                <div className="muted">Last worked {b.last_ok_at ? formatDate(b.last_ok_at) : "never"}</div>
              </td>
              <td className="small">{b.last_error ?? ""}</td>
              <td className="nowrap">
                <button type="button" onClick={() => switchOff(b.id)}>
                  Switch off
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** The newest backup, a reminder after a week, and a button to make one. */
function Backups() {
  const status = useLoad(() => api.backupStatus(), "backup");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const s = status.data;
  if (!s) return null;

  async function backUp() {
    setBusy(true);
    setError(null);
    try {
      status.setData(await api.makeBackup());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`panel backups${s.remind ? " remind" : ""}`}>
      <h2>Backups</h2>
      <p>
        {s.latest === null
          ? "No backup yet. Your statuses, notes and applied dates exist only in the database, so keep a copy."
          : s.age_days === 0
            ? "Last backup: today."
            : `Last backup: ${formatDate(s.taken_at)}, ${s.age_days} ${s.age_days === 1 ? "day" : "days"} ago.`}
        {s.remind && s.latest !== null && " Time for a new one."}
      </p>
      {error && <p className="error">{error}</p>}
      <button type="button" className={s.remind ? "primary" : ""} disabled={busy} onClick={backUp}>
        {busy ? "Backing up…" : "Back up now"}
      </button>
      <p className="hint">
        Copies go in the data folder as <code>jobradar-backup-&lt;date&gt;.db</code>; <code>jobradar backup</code> does
        the same.
      </p>
    </section>
  );
}
