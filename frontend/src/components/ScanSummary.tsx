// After a scan: what it found, with a link to just those jobs. Stays until
// you open them, close it, or start another scan.

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { plural } from "../format";
import { useApp } from "../state";

export default function ScanSummary() {
  const { scanDone, dismissScanDone } = useApp();
  const navigate = useNavigate();
  return (
    <AnimatePresence>
      {scanDone && (
        <motion.div
          key={scanDone.since}
          className="scan-summary-wrap"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.12 } }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        >
          <Summary {...scanDone} onOpen={(to) => { navigate(to); dismissScanDone(); }} onClose={dismissScanDone} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Summary({ found, postings, closed, failed, since, onOpen, onClose }: {
  found: number; postings: number; closed: number; failed: number; since: string;
  onOpen: (to: string) => void; onClose: () => void;
}) {

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
          onClick={() => onOpen(`/?new_since=${encodeURIComponent(since)}`)}
        >
          Show {found === 1 ? "it" : "them"}
        </button>
      )}
      <button type="button" className="quiet" aria-label="Close" onClick={onClose}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
