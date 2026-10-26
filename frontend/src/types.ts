// Shapes returned by the Python API (jobradar/web/app.py). Keep in step with it.

export type JobStatus =
  | "new"
  | "saved"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "not_interested";

export type CompanyStatus = "none" | "target" | "watching" | "ignored";

export type Workplace = "remote" | "hybrid" | "onsite" | "unknown";

export interface Meta {
  provinces: { code: string; name: string }[];
  job_statuses: JobStatus[];
  company_statuses: CompanyStatus[];
  size_bands: string[];
  systems: string[];
  workplaces: Workplace[];
  open_jobs: number;
  companies: number;
}

export interface JobSummary {
  id: number;
  title: string;
  url: string;
  company_id: number;
  company: string;
  company_status: CompanyStatus;
  employee_count: number | null;
  size_band: string;
  system: string;
  board_confirmed: boolean;
  location: string;
  provinces: string[];
  workplace: Workplace;
  posted_at: string | null;
  salary: string | null;
  status: JobStatus;
  notes: string;
  applied_at: string | null;
  first_seen: string;
  last_seen: string;
  closed_at: string | null;
}

export interface JobPage {
  total: number;
  page: number;
  page_size: number;
  items: JobSummary[];
}

export interface JobLocation {
  label: string;
  city: string | null;
  province: string | null;
  country: string | null;
  remote: boolean;
  in_canada: boolean;
}

export interface JobEvent {
  at: string;
  field: string;
  old: string | null;
  new: string | null;
}

export interface JobDetail extends JobSummary {
  department: string | null;
  employment_type: string | null;
  description: string | null;
  status_changed_at: string | null;
  locations: JobLocation[];
  events: JobEvent[];
  links: { job: string; careers: string | null; linkedin: string };
}

export interface JobTracking {
  id: number;
  status: JobStatus;
  notes: string;
  applied_at: string | null;
  status_changed_at: string | null;
}

export interface Board {
  id: number;
  system: string;
  slug_or_url: string;
  confirmed: boolean;
  enabled: boolean;
  last_scanned_at: string | null;
  last_error: string | null;
  total_open: number | null;
}

export interface Company {
  id: number;
  name: string;
  canadian: boolean;
  status: CompanyStatus;
  notes: string;
  careers_url: string | null;
  employee_count: number | null;
  size_band: string;
  size_source: string | null;
  canada_open: number;
  total_open: number | null;
  boards: Board[];
}

export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  filters: Record<string, string>;
  use_for_sources: boolean;
}

export interface ScanBoardResult {
  company: string;
  system: string;
  ok: boolean;
  jobs_canada: number;
  jobs_new: number;
  error: string | null;
}

export interface ScanState {
  running: boolean;
  company: string | null;
  started_at: string | null;
  finished_at: string | null;
  boards_total: number;
  boards_done: number;
  boards_failed: number;
  jobs_new: number;
  jobs_closed: number;
  scan_id: number | null;
  error: string | null;
  recent: ScanBoardResult[];
}

export interface ScanRecord {
  id: number;
  started_at: string;
  finished_at: string | null;
  boards_ok: number;
  boards_failed: number;
  jobs_new: number;
  jobs_closed: number;
}

export interface ScanResultRow {
  id: number;
  board_id: number;
  ok: number;
  jobs_seen: number;
  jobs_canada: number;
  error: string | null;
  ms: number | null;
  system: string;
  slug_or_url: string;
  company_id: number;
  company: string;
}
