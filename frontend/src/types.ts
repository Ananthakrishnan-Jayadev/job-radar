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
  /** Every job system a board can use. */
  systems: string[];
  /** Job systems that currently have jobs: the ones worth filtering by. */
  systems_in_use: string[];
  workplaces: Workplace[];
  /** Role groups from roles.toml; enabled ones are shown by default. */
  role_categories: { name: string; label: string; enabled: boolean }[];
  open_jobs: number;
  companies: number;
  /** Experience levels to filter by, ending with "unknown". */
  levels: string[];
  /** Filter values for the years of experience asked, ending with "none". */
  year_bands: string[];
  /** Open wanted jobs missing a level or years, not yet asked about, which Ollama can read. */
  levels_to_ask: number;
  ollama_model: string;
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
  /** Role groups the title belongs to (software, data, ai, adjacent). */
  roles: string[];
  /** intern / entry / mid / senior / lead, or null when not known. */
  level: string | null;
  /** The fewest years of experience the description asks for. */
  min_years: number | null;
  /** "title", "years", "none" or "ollama:<model>"; null when not worked out. */
  level_source: string | null;
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
  /** Scans failed in a row, up to the latest (0 when the last one worked). */
  failures: number;
}

export interface SizeSuggestion {
  source: string;
  employees: number;
  as_of?: string | null;
  wikidata_id?: string;
  label?: string;
  description?: string;
  url?: string;
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
  size_suggestion: SizeSuggestion | null;
  hq: string | null;
  canada_open: number;
  /** Open Canadian jobs in the wanted role groups. */
  wanted_open: number;
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

export interface DetectedBoard {
  system: string;
  slug_or_url: string;
  how: "link" | "page" | "guess";
  confidence: "certain" | "likely" | "possible";
  note: string;
  jobs_canada: number | null;
  jobs_total: number | null;
}

export interface Candidate {
  id: number;
  name: string;
  tagline: string | null;
  employees: number | null;
  size_band: string;
  hq_country: string | null;
  hq_province: string | null;
  hq_city: string | null;
  jobs_url: string | null;
  detected_system: string | null;
  detected_slug: string | null;
  detect_note: string | null;
  company_id: number | null;
  company_name: string | null;
  decision: "pending" | "approved" | "rejected";
  first_seen: string;
  gone_at: string | null;
}

export interface TaskState {
  name: string | null;
  running: boolean;
  done: number;
  total: number;
  result: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
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

/** A tracked job on the Applications page. */
export interface TrackedJob {
  id: number;
  title: string;
  url: string;
  status: JobStatus;
  applied_at: string | null;
  status_changed_at: string | null;
  closed_at: string | null;
  first_seen: string;
  level: string | null;
  company_id: number;
  company: string;
  /** Days since the status last changed (or since applying). */
  days_since_change: number | null;
  days_since_applied: number | null;
}

export interface Applications {
  today: string;
  /** Jobs in each status except "new". */
  counts: Record<Exclude<JobStatus, "new">, number>;
  /** Jobs ever applied to. */
  applied_total: number;
  /** Of those, how many got an answer (interview, offer or no). */
  heard_back: number;
  interviews: number;
  follow_up_days: number;
  /** The last 12 weeks, oldest first; each starts on a Monday. */
  per_week: { week: string; applied: number }[];
  follow_up: TrackedJob[];
  active: TrackedJob[];
  saved: TrackedJob[];
  recent: { at: string; old: string | null; new: string | null; id: number; title: string; company_id: number;
            company: string }[];
}

export interface BackupStatus {
  latest: string | null;
  taken_at: string | null;
  age_days: number | null;
  /** True when there's no backup, or the newest is a week old or more. */
  remind: boolean;
}

export interface FailingBoard {
  id: number;
  system: string;
  slug_or_url: string;
  last_error: string | null;
  company_id: number;
  company: string;
  last_ok_at: string | null;
  failures: number;
}

/** What a job link's page says, to check before saving (jobradar/manual.py). */
export interface JobDraft {
  url: string;
  title: string;
  company: string;
  /** An existing company that matches, by the link's job board or by name. */
  company_id: number | null;
  city: string;
  province: string;
  country: string;
  remote: boolean;
  description: string;
  posted_at: string | null;
  employment_type: string;
  salary: string;
  found: string[];
  note: string;
}

export interface SavedResume {
  name: string;
  size: number;
  saved_at: string;
}

/** What "Apply" needs: Playwright, your profile, a résumé (jobradar/web/app.py). */
export interface ApplySetup {
  /** How to install the browser, or null when it's ready. */
  browser: string | null;
  profile: { ok: boolean; missing: string[]; error: string | null };
  resumes: SavedResume[];
}

/** The application window's progress (jobradar/web/applier.py). */
export interface ApplyState {
  phase: "opening" | "filling" | "ready" | "submitted" | "closed" | "error" | null;
  job_id?: number;
  title?: string;
  company?: string;
  resume?: string;
  message?: string;
  filled?: { label: string; check: boolean }[];
  todo?: { label: string; required: boolean; why: string }[];
}
