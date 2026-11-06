// After a scan: what it found, with a link to just those jobs. Stays until
// you open them, close it, or start another scan.

import { X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { plural } from "../format";
import { useApp } from "../state";

export default function ScanSummary() {
  const { scanDone, dismissScanDone } = useApp();
  const navigate = useNavigate();
  if (!scanDone) return null;
  const { found, postings, closed, failed, since } = scanDone;

  const extra = [
    `${plural(postings, "new posting")} in all`,
    closed ? plural(closed, "closed", "closed") : null,
    failed ? `${plural(failed, "board")} failed` : null,
  ].filter(Boolean);

  return (
    <div className="scan-summary" role="status">
      <p>
        <strong>
          Scan finished: {found ? `${plural(found, "new job")} for you` : "nothing new for you"}
        </strong>{" "}
        <span className="muted">({extra.join(", ")})</span>
      </p>
      {found > 0 && (
        <button
          type="button"
          className="primary"
          onClick={() => {
            navigate(`/?new_since=${encodeURIComponent(since)}`);
            dismissScanDone();
          }}
        >
          Show {found === 1 ? "it" : "them"}
        </button>
      )}
      <button type="button" className="quiet" aria-label="Close" onClick={dismissScanDone}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
