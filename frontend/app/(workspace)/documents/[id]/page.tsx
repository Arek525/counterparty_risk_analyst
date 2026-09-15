"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorNotice, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatLocation } from "@/lib/format";
import type { DocumentRecord } from "@/lib/types";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [modelStatus, setModelStatus] = useState<{status: string; error?: string | null} | null>(null);
  async function load() {
    setError("");
    try {
      setDocument(await api<DocumentRecord>(`/api/documents/${id}`));
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }
  useEffect(() => {
    void load();
  }, [id]);
  useEffect(() => {
    if (document) {
      const chunk = new URLSearchParams(globalThis.location.search).get(
        "chunk",
      );
      if (chunk)
        globalThis.document
          .getElementById(`chunk-${chunk}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [document?.id]);
  useEffect(() => {
    const refresh = () => {
      void api<{status: string; error?: string | null}>("/api/embedding-status").then(setModelStatus).catch(() => {});
      void api<DocumentRecord>(`/api/documents/${id}`).then(setDocument).catch(() => {});
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [id]);
  async function reindex() {
    setIndexing(true);
    setError("");
    try {
      await api(`/api/documents/${id}/reindex`, {method: "POST"});
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setIndexing(false);
    }
  }
  async function remove() {
    if (
      !confirm(
        "Delete this document? A document retained by a saved version cannot be deleted.",
      )
    )
      return;
    setDeleting(true);
    setError("");
    try {
      await api(`/api/documents/${id}`, { method: "DELETE" });
      router.push(
        document?.case_id ? `/cases/${document.case_id}` : "/policies",
      );
    } catch (reason) {
      setError(errorMessage(reason));
      setDeleting(false);
    }
  }
  if (!document && !error) return <Spinner label="Loading source…" />;
  if (!document) return <ErrorNotice message={error} retry={load} />;
  return (
    <>
      <PageHeader
        eyebrow={
          document.kind === "policy" ? "Policy document" : "Counterparty evidence"
        }
        title={document.filename}
        description={`Version ${document.version} · ${formatDate(document.created_at)}`}
        actions={
          <>
            <a
              className="button button-secondary"
              href={`/api/documents/${document.id}/download`}
            >
              Download original
            </a>
            {user?.role !== "auditor" && (
              <button
                className="button button-danger"
                disabled={deleting}
                onClick={remove}
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            )}
          </>
        }
      />
      {error && <ErrorNotice message={error} />}
      <div className="notice notice-info" style={{marginBottom: 18}}>
        <p aria-live="polite">Semantic index: <strong>{document.index_status ?? "pending"}</strong> · Local model: {modelStatus?.status ?? "checking"}</p>
        {document.index_error && <p>{document.index_error}</p>}
        {modelStatus?.error && <p>{modelStatus.error}</p>}
        <p>Indexing runs in the background. Source text and lexical analysis remain available.</p>
        {user?.role !== "auditor" && <button className="button button-small button-secondary" disabled={indexing} onClick={reindex}>{indexing ? "Queuing…" : "Reindex document"}</button>}
      </div>
      {document.kind === "evidence" && (
        <div className="notice notice-info" style={{ marginBottom: 18 }}>
          <p>
            <strong>Source type:</strong>{" "}
            {document.evidence_type === "independent"
              ? "independent evidence"
              : "counterparty declaration"}
          </p>
        </div>
      )}
      <section className="card">
        <div className="card-header">
          <h2>Extracted source text</h2>
          <StatusBadge value="neutral">
            {document.chunks?.length ?? 0} chunks
          </StatusBadge>
        </div>
        <div className="card-body stack">
          {document.chunks?.map((chunk) => (
            <article
              className="source-document"
              id={`chunk-${chunk.id}`}
              key={chunk.id}
            >
              <div className="subtle" style={{ marginBottom: 9 }}>
                {formatLocation(chunk.location)} ·{" "}
                <span className="mono">{chunk.id}</span>
              </div>
              <div>{chunk.text}</div>
            </article>
          )) ?? (
            <p className="subtle">
              This document contains no text chunks.
            </p>
          )}
        </div>
      </section>
      <p style={{ marginTop: 18 }}>
        <Link
          className="arrow-link"
          href={document.case_id ? `/cases/${document.case_id}` : "/policies"}
        >
          ← Back
        </Link>
      </p>
    </>
  );
}
