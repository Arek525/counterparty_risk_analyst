import type { FindingStatus, Role, SourceLocation } from "./types";

export const roleLabels: Record<Role, string> = {
  analyst: "Analityk",
  reviewer: "Recenzent",
  auditor: "Audytor",
  administrator: "Administrator",
};

export const findingLabels: Record<FindingStatus, string> = {
  pass: "Spełnione",
  fail: "Niespełnione",
  unknown: "Brak danych",
  conflict: "Sprzeczność",
  not_applicable: "Nie dotyczy",
};

export const statusLabels: Record<string, string> = {
  draft: "Wersja robocza",
  approved: "Zatwierdzona",
  queued: "W kolejce",
  running: "Analiza trwa",
  awaiting_review: "Oczekuje na decyzję",
  completed: "Zakończona",
  failed: "Błąd",
  proposed: "Do zatwierdzenia",
  executing: "Wysyłanie",
  executed: "Wykonano",
  succeeded: "Wykonano",
  accepted: "Zaakceptowano",
  rejected: "Odrzucono",
  needs_information: "Potrzebne informacje",
};

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("pl-PL", {
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
  if (value.page !== undefined) parts.push(`strona ${value.page}`);
  if (value.line_start !== undefined)
    parts.push(
      value.line_end && value.line_end !== value.line_start
        ? `wiersze ${value.line_start}–${value.line_end}`
        : `wiersz ${value.line_start}`,
    );
  return parts.join(", ") || "lokalizacja źródłowa";
}
