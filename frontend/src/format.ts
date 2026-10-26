// Words and formats shown in the UI, in one place so they stay consistent.

import type { CompanyStatus, JobStatus, Workplace } from "./types";

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  new: "New",
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  not_interested: "Not interested",
};

export const COMPANY_STATUS_LABEL: Record<CompanyStatus, string> = {
  none: "No status",
  target: "Target",
  watching: "Watching",
  ignored: "Ignored",
};

export const SIZE_LABEL: Record<string, string> = {
  "<50": "Under 50",
  "50-199": "50–199",
  "200-999": "200–999",
  "1000-4999": "1,000–4,999",
  "5000+": "5,000+",
  unknown: "Unknown",
};

export const WORKPLACE_LABEL: Record<Workplace, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "On-site",
  unknown: "Not stated",
};

export const SYSTEM_LABEL: Record<string, string> = {
  ashby: "Ashby",
  bamboohr: "BambooHR",
  breezy: "Breezy HR",
  greenhouse: "Greenhouse",
  lever: "Lever",
  recruitee: "Recruitee",
  rippling: "Rippling",
  smartrecruiters: "SmartRecruiters",
  workable: "Workable",
  workday: "Workday",
  successfactors: "SAP SuccessFactors",
};

export const SIZE_SOURCE_LABEL: Record<string, string> = {
  manual: "entered by you",
  stillhiring: "from stillhiring.today",
  imported: "from your imported list",
  wikidata: "from Wikidata",
  estimate: "estimated from open roles",
};

export const CONFIDENCE_LABEL: Record<string, string> = {
  certain: "From its careers link",
  likely: "Found on its careers page",
  possible: "Guessed from its name",
};

const MONTH_DAY = new Intl.DateTimeFormat("en-CA", { month: "short", day: "numeric" });
const FULL_DATE = new Intl.DateTimeFormat("en-CA", { month: "short", day: "numeric", year: "numeric" });
const DATE_TIME = new Intl.DateTimeFormat("en-CA", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** "Oct 24" this year, "Oct 24, 2024" otherwise; "—" when unknown. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  // Plain dates ("2026-10-24") are calendar days, not UTC midnight.
  const date = value.length === 10 ? new Date(`${value}T12:00:00`) : new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.getFullYear() === new Date().getFullYear() ? MONTH_DAY.format(date) : FULL_DATE.format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : DATE_TIME.format(date);
}

export function formatCount(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : n.toLocaleString("en-CA");
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

export function duration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const seconds = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function boardLabel(system: string, slugOrUrl: string): string {
  const name = SYSTEM_LABEL[system] ?? system;
  if (system === "workday") {
    const site = slugOrUrl.split("/").filter(Boolean).pop();
    return `${name}: ${site ?? slugOrUrl}`;
  }
  return `${name}: ${slugOrUrl}`;
}
