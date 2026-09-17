import type { FindingStatus, Role } from "./types";

export const roleLabels: Record<Role, string> = {
  analyst: "Analyst",
  reviewer: "Reviewer",
};

export const findingLabels: Record<FindingStatus, string> = {
  pass: "Pass",
  fail: "Fail",
  unknown: "Insufficient evidence",
  conflict: "Conflict",
  not_applicable: "Not applicable",
};

export const statusLabels: Record<string, string> = {
  draft: "Draft",
  approved: "Approved",
  queued: "Queued",
  running: "Analysis in progress",
  awaiting_review: "Awaiting decision",
  completed: "Completed",
  failed: "Failed",
  succeeded: "Completed",
  accepted: "Accepted",
  rejected: "Rejected",
  needs_information: "Information required",
};

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

const fieldLabels: Record<string, string> = {
  retention_days: "Data deletion period",
  notification_hours: "Incident notification period",
  hosting_region: "Hosting region",
  subprocessors_region: "Subprocessor region",
  mfa: "Multi-factor authentication",
  encryption_at_rest: "Encryption at rest",
  dpa_signed: "Signed data processing agreement",
  personal_data: "Personal data processing",
  privileged_access: "Privileged access",
  business_criticality: "Business criticality",
  purpose: "Relationship purpose",
  data_shared: "Data shared",
  system_access: "System access",
};

export function formatApplicability(conditions: Record<string, unknown> = {}): string {
  if (!Object.keys(conditions).length) return "All relationships";
  return Object.entries(conditions).map(([key, value]) => {
    if (typeof value === "boolean") {
      if (key === "personal_data") return value
        ? "The counterparty processes personal data"
        : "The counterparty does not process personal data";
      if (key === "privileged_access") return value
        ? "The counterparty has privileged access"
        : "The counterparty does not have privileged access";
      const label = fieldLabels[key] ?? titleCase(key);
      return `${label}: ${value ? "Yes" : "No"}`;
    }
    return `${fieldLabels[key] ?? titleCase(key)}: ${String(value)}`;
  }).join("; ");
}
