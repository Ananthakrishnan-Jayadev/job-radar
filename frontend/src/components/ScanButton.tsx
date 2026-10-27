import NumberFlow from "@number-flow/react";
import { RefreshCw } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { useApp } from "../state";

/** "Scan now" in the top bar; shows progress while a scan runs anywhere in the app. */
export default function ScanButton() {
  const { scan, startScan, scanError } = useApp();
  if (scan?.running) {
    const pct = scan.boards_total ? Math.round((100 * scan.boards_done) / scan.boards_total) : 0;
    return (
      <Link to="/scans" className="scan-progress" aria-live="polite">
        <motion.span
          className="bar"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 22 }}
        />
        <span className="text">
          Scanning {scan.company ?? "all companies"}: <NumberFlow value={scan.boards_done} /> of {scan.boards_total} boards
        </span>
      </Link>
    );
  }
  return (
    <div className="scan-button">
      <motion.button type="button" className="primary" whileTap={{ scale: 0.96 }} onClick={() => startScan()}>
        <RefreshCw size={15} strokeWidth={2.2} aria-hidden="true" />
        Scan now
      </motion.button>
      {scanError && (
        <span className="error-inline" role="alert">
          {scanError}
        </span>
      )}
    </div>
  );
}
