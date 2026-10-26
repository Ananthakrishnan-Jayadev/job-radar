import { Link } from "react-router-dom";
import { useApp } from "../state";

/** "Scan now" in the top bar; shows progress while a scan runs anywhere in the app. */
export default function ScanButton() {
  const { scan, startScan, scanError } = useApp();
  if (scan?.running) {
    const pct = scan.boards_total ? Math.round((100 * scan.boards_done) / scan.boards_total) : 0;
    return (
      <Link to="/scans" className="scan-progress" aria-live="polite">
        <span className="bar" style={{ width: `${pct}%` }} />
        <span className="text">
          Scanning {scan.company ?? "all companies"}: {scan.boards_done} of {scan.boards_total} boards
        </span>
      </Link>
    );
  }
  return (
    <div className="scan-button">
      <button type="button" className="primary" onClick={() => startScan()}>
        Scan now
      </button>
      {scanError && (
        <span className="error-inline" role="alert">
          {scanError}
        </span>
      )}
    </div>
  );
}
