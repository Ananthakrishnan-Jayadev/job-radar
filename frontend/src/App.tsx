import { NavLink, Route, Routes } from "react-router-dom";
import ScanButton from "./components/ScanButton";
import CompaniesPage from "./pages/CompaniesPage";
import CompanyPage from "./pages/CompanyPage";
import JobPage from "./pages/JobPage";
import JobsPage from "./pages/JobsPage";
import SavedSearchesPage from "./pages/SavedSearchesPage";
import ScansPage from "./pages/ScansPage";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand" end>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="8" cy="8" r="6" />
            <circle cx="8" cy="8" r="2" className="dot" />
          </svg>
          Job Radar
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Jobs
          </NavLink>
          <NavLink to="/companies">Companies</NavLink>
          <NavLink to="/saved">Saved searches</NavLink>
          <NavLink to="/scans">Scans</NavLink>
        </nav>
        <ScanButton />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/jobs/:id" element={<JobPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/companies/:id" element={<CompanyPage />} />
          <Route path="/saved" element={<SavedSearchesPage />} />
          <Route path="/scans" element={<ScansPage />} />
          <Route path="*" element={<p className="empty">There's no page here. Pick one from the menu above.</p>} />
        </Routes>
      </main>
    </div>
  );
}
