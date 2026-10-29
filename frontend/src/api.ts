// Thin typed client for the Python API. Every call goes to the same server
// that serves this page, so there is no base URL to configure.

import type {
  Applications,
  ApplySetup,
  ApplyState,
  BackupStatus,
  JobDraft,
  FailingBoard,
  Candidate,
  Company,
  DetectedBoard,
  CompanyStatus,
  JobDetail,
  JobPage,
  JobStatus,
  JobTracking,
  Meta,
  SavedSearch,
  ScanRecord,
  ScanResultRow,
  ScanState,
  TaskState,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data: unknown = await response.json();
      if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Upload a résumé (a form post, not JSON). */
async function uploadResume(file: File): Promise<{ name: string; resumes: ApplySetup["resumes"] }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/resumes", { method: "POST", body: form });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "Upload failed");
  return data;
}

export interface JobPatch {
  status?: JobStatus;
  notes?: string;
  applied_at?: string | null;
}

export interface CompanyPatch {
  status?: CompanyStatus;
  notes?: string;
  employee_count?: number | null;
  canadian?: boolean;
  careers_url?: string | null;
}

export interface NewBoard {
  system: string;
  slug_or_url: string;
}

export const api = {
  meta: () => request<Meta>("GET", "/api/meta"),
  visit: () => request<{ previous: string | null }>("POST", "/api/visit"),

  jobs: (params: URLSearchParams) => request<JobPage>("GET", `/api/jobs?${params}`),
  provinceCounts: (params: URLSearchParams) =>
    request<Record<string, number>>("GET", `/api/jobs/provinces?${params}`),
  job: (id: number) => request<JobDetail>("GET", `/api/jobs/${id}`),
  patchJob: (id: number, patch: JobPatch) => request<JobTracking>("PATCH", `/api/jobs/${id}`, patch),
  exportUrl: (params: URLSearchParams) => `/api/jobs.csv?${params}`,

  companies: (params: URLSearchParams) => request<Company[]>("GET", `/api/companies?${params}`),
  company: (id: number) => request<Company>("GET", `/api/companies/${id}`),
  addCompany: (body: { name: string; canadian: boolean; careers_url?: string | null; board?: NewBoard }) =>
    request<Company>("POST", "/api/companies", body),
  patchCompany: (id: number, patch: CompanyPatch) => request<Company>("PATCH", `/api/companies/${id}`, patch),
  addBoard: (companyId: number, board: NewBoard) =>
    request<Company>("POST", `/api/companies/${companyId}/boards`, board),
  patchBoard: (id: number, patch: { enabled?: boolean; confirmed?: boolean }) =>
    request<unknown>("PATCH", `/api/boards/${id}`, patch),

  acceptSize: (id: number) => request<Company>("POST", `/api/companies/${id}/accept-size`),
  lookUpSize: (id: number) => request<{ result: string }>("POST", "/api/enrich", { company_id: id }),
  fillAllSizes: () => request<TaskState>("POST", "/api/enrich", {}),
  detect: (body: { name: string; careers_url?: string | null; canadian: boolean }) =>
    request<DetectedBoard[]>("POST", "/api/detect", body),
  findMissingBoards: () => request<TaskState>("POST", "/api/find-boards"),
  askLevels: () => request<TaskState>("POST", "/api/levels/ask"),
  readJobLink: (url: string) =>
    request<{ existing?: number; draft?: JobDraft }>("POST", "/api/jobs/from-link", { url }),
  addManualJob: (job: Omit<JobDraft, "found" | "note" | "country"> & { status: JobStatus }) =>
    request<{ id: number; new: boolean }>("POST", "/api/jobs/manual", job),
  companyHistory: (id: number) => request<{ day: string; open: number }[]>("GET", `/api/companies/${id}/history`),
  applySetup: () => request<ApplySetup>("GET", "/api/apply/setup"),
  uploadResume,
  applyToJob: (id: number, resume: string) => request<ApplyState>("POST", `/api/jobs/${id}/apply`, { resume }),
  applyState: () => request<ApplyState>("GET", "/api/apply/current"),
  backupStatus: () => request<BackupStatus>("GET", "/api/backup"),
  makeBackup: () => request<BackupStatus>("POST", "/api/backup"),
  failingBoards: () => request<{ after: number; boards: FailingBoard[] }>("GET", "/api/boards/failing"),
  applications: () => request<Applications>("GET", "/api/applications"),
  currentTask: () => request<TaskState>("GET", "/api/tasks/current"),

  candidates: (params: URLSearchParams) =>
    request<{ refreshed_at: string | null; items: Candidate[] }>("GET", `/api/candidates?${params}`),
  refreshCandidates: () =>
    request<{ total: number; new: number; gone: number; canadian: number; linked: number; sizes: number }>(
      "POST",
      "/api/candidates/refresh",
    ),
  approveCandidate: (id: number, board?: NewBoard) =>
    request<{ company_id: number }>("POST", `/api/candidates/${id}/approve`, board ?? {}),
  rejectCandidate: (id: number) => request<unknown>("POST", `/api/candidates/${id}/reject`),
  restoreCandidate: (id: number) => request<unknown>("POST", `/api/candidates/${id}/restore`),
  detectCandidate: (id: number) => request<{ options: DetectedBoard[] }>("POST", `/api/candidates/${id}/detect`),
  detectAllCandidates: () => request<TaskState>("POST", "/api/candidates/detect-all"),

  savedSearches: () => request<SavedSearch[]>("GET", "/api/saved-searches"),
  saveSearch: (body: { name: string; query: string; filters: Record<string, string>; use_for_sources: boolean }) =>
    request<SavedSearch>("POST", "/api/saved-searches", body),
  patchSavedSearch: (id: number, patch: { name?: string; use_for_sources?: boolean }) =>
    request<SavedSearch>("PATCH", `/api/saved-searches/${id}`, patch),
  deleteSavedSearch: (id: number) => request<void>("DELETE", `/api/saved-searches/${id}`),

  startScan: (companyId?: number) =>
    request<ScanState>("POST", "/api/scans", companyId === undefined ? {} : { company_id: companyId }),
  currentScan: () => request<ScanState>("GET", "/api/scans/current"),
  scans: () => request<ScanRecord[]>("GET", "/api/scans"),
  scan: (id: number) => request<{ scan: ScanRecord; results: ScanResultRow[] }>("GET", `/api/scans/${id}`),
};
