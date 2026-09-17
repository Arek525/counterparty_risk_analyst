"use client";

import type { ReactNode } from "react";
import { Icon } from "./icons";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice notice-error" role="alert">
      <div>
        <strong>We couldn't complete the operation</strong>
        <p>{message}</p>
      </div>
      {retry && (
        <button className="button button-small button-quiet" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-mark">○</span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function StatusBadge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  const tone: Record<string, string> = {
    approved: "success",
    completed: "success",
    pass: "success",
    succeeded: "success",
    Low: "success",
    failed: "danger",
    fail: "danger",
    rejected: "danger",
    High: "danger",
    conflict: "warning",
    Medium: "warning",
    unknown: "neutral",
    queued: "info",
    running: "info",
    awaiting_review: "warning",
    needs_information: "warning",
    draft: "neutral",
    proposed: "neutral",
    executing: "info",
    executed: "success",
    not_applicable: "neutral",
  };
  return (
    <span className={`badge badge-${tone[value] ?? "neutral"}`}>
      {children ?? value}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}

export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" onClick={close} aria-label="Close">
            <Icon name="close" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
