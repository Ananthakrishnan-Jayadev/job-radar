import { AnimatePresence, motion } from "motion/react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import ScanButton from "./components/ScanButton";
import ApplicationsPage from "./pages/ApplicationsPage";
import CandidatesPage from "./pages/CandidatesPage";
import CompaniesPage from "./pages/CompaniesPage";
import CompanyPage from "./pages/CompanyPage";
import JobPage from "./pages/JobPage";
import JobsPage from "./pages/JobsPage";
import SavedSearchesPage from "./pages/SavedSearchesPage";
import ScansPage from "./pages/ScansPage";
import { useApp } from "./state";
import { ThemeToggle } from "./theme";

const NAV = [
  { to: "/", label: "Jobs", end: true },
  { to: "/applications", label: "Applications" },
  { to: "/companies", label: "Companies" },
  { to: "/candidates", label: "Candidates" },
  { to: "/saved", label: "Saved searches" },
  { to: "/scans", label: "Scans" },
];

export default function App() {
  const location = useLocation();
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand" end>
          <RadarMark />
          Job Radar
        </NavLink>
        <nav aria-label="Main">
          {NAV.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end}>
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-pill"
                      className="pill"
                      transition={{ type: "spring", stiffness: 500, damping: 38 }}
                    />
                  )}
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <ScanButton />
          <ThemeToggle />
        </div>
      </header>
      <main>
        {/* Pages cross-fade; filter changes (same path, new query) don't. */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <Routes location={location}>
              <Route path="/" element={<JobsPage />} />
              <Route path="/jobs/:id" element={<JobPage />} />
              <Route path="/applications" element={<ApplicationsPage />} />
              <Route path="/companies" element={<CompaniesPage />} />
              <Route path="/companies/:id" element={<CompanyPage />} />
              <Route path="/candidates" element={<CandidatesPage />} />
              <Route path="/saved" element={<SavedSearchesPage />} />
              <Route path="/scans" element={<ScansPage />} />
              <Route path="*" element={<p className="empty">There's no page here. Pick one from the menu above.</p>} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

/** The logo: a radar whose sweep turns while a scan is running. */
function RadarMark() {
  const { scan } = useApp();
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" />
      <circle cx="8" cy="8" r="3.5" opacity="0.45" />
      <path d="M8 8 L8 1.5 A6.5 6.5 0 0 1 14.2 6 Z" className={`sweep${scan?.running ? " animate-sweep" : ""}`} />
      <circle cx="8" cy="8" r="1.6" className="dot" />
    </svg>
  );
}
