"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorNotice, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

export default function AuditPage() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [queryReady, setQueryReady] = useState(false);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    setCaseId(new URLSearchParams(globalThis.location.search).get("case_id"));
    setQueryReady(true);
  }, []);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setEvents(
        await api<AuditEvent[]>(
          caseId
            ? `/api/audit?case_id=${encodeURIComponent(caseId)}`
            : "/api/audit",
        ),
      );
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (queryReady) void load();
  }, [caseId, queryReady]);
  return (
    <>
      <PageHeader
        eyebrow="Immutable record"
        title="Activity history"
        description={
          caseId
            ? "Events for the selected case, newest first."
            : "Organization events, newest first."
        }
        actions={
          caseId && (
            <Link className="button button-quiet" href={`/cases/${caseId}`}>
              Back to case
            </Link>
          )
        }
      />
      {error && <ErrorNotice message={error} retry={load} />}{" "}
      {loading ? (
        <Spinner label="Loading activity…" />
      ) : events.length === 0 ? (
        <section className="card">
          <EmptyState
            title="No events"
            description="Activity will appear as you work with policies, cases, and analyses."
          />
        </section>
      ) : (
        <section className="card">
          <div className="card-header">
            <h2>Events</h2>
            <span className="subtle">{events.length} entries</span>
          </div>
          <div className="card-body">
            <div className="timeline">
              {events.map((event) => (
                <article className="timeline-item" key={event.id}>
                  <div className="timeline-rail">
                    <span className="timeline-dot" />
                  </div>
                  <div className="timeline-content">
                    <h3>{titleCase(event.event)}</h3>
                    <p>
                      {event.actor_email ?? event.actor_name ??
                        (event.actor_id
                          ? `User ${event.actor_id}`
                          : "System")}{" "}
                      · {formatDate(event.created_at)}
                    </p>
                    {event.details && Object.keys(event.details).length > 0 && (
                      <details>
                        <summary className="subtle">Details</summary>
                        <pre className="source-document mono">
                          {JSON.stringify(event.details, null, 2)}
                        </pre>
                      </details>
                    )}
                    {event.run_id && (
                      <Link
                        className="arrow-link"
                        href={`/runs/${event.run_id}`}
                      >
                        Open analysis →
                      </Link>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}
    </>
  );
}
