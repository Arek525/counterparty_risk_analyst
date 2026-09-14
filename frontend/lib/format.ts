import type { FindingStatus, Role, SourceLocation } from "./types";

export const roleLabels: Record<Role, string> = {
  analyst: "Analyst",
  reviewer: "Reviewer",
  auditor: "Auditor",
  administrator: "Administrator",
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
  proposed: "Awaiting approval",
  executing: "Submitting",
  executed: "Executed",
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

export function formatLocation(value: SourceLocation): string {
  if (typeof value === "string") return value;
  const parts: string[] = [];
  if (value.page !== undefined) parts.push(`page ${value.page}`);
  if (value.line_start !== undefined)
    parts.push(
      value.line_end && value.line_end !== value.line_start
        ? `lines ${value.line_start}–${value.line_end}`
        : `line ${value.line_start}`,
    );
  return parts.join(", ") || "source location";
}
