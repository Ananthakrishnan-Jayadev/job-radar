// Thin typed client for the Python API. Every call goes to the same server
// that serves this page, so there is no base URL to configure.

import type {
  Company,
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
  addCompany: (body: { name: string; canadian: boolean; careers_url?: string; board?: NewBoard }) =>
    request<Company>("POST", "/api/companies", body),
  patchCompany: (id: number, patch: CompanyPatch) => request<Company>("PATCH", `/api/companies/${id}`, patch),
  addBoard: (companyId: number, board: NewBoard) =>
    request<Company>("POST", `/api/companies/${companyId}/boards`, board),
  patchBoard: (id: number, patch: { enabled?: boolean; confirmed?: boolean }) =>
    request<unknown>("PATCH", `/api/boards/${id}`, patch),

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
