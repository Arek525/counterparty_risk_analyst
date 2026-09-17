"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ErrorNotice, PageHeader, Spinner } from "@/components/ui";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { locateSource } from "@/lib/source";
import type { DocumentRecord, PolicyVersion } from "@/lib/types";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [error, setError] = useState("");
  const [policies, setPolicies] = useState<PolicyVersion[]>([]);
  const [source, setSource] = useState<{chunk: string | null; quote: string | null}>({chunk: null, quote: null});
  const highlight = useRef<HTMLElement>(null);
  const selection = useMemo(() => document ? locateSource(document, source.chunk, source.quote) : {}, [document, source]);
  const [extracting, setExtracting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [modelStatus, setModelStatus] = useState<{status: string; error?: string | null} | null>(null);
  async function load() {
    setError("");
    try {
      const value = await api<DocumentRecord>(`/api/documents/${id}`);
      setDocument(value);
      if (value.kind === "policy") setPolicies((await api<PolicyVersion[]>("/api/policies")).filter((policy) => policy.document_ids.includes(id)));
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }
  useEffect(() => {
    void load();
  }, [id]);
  useEffect(() => {
    const readSource = () => {
      const query = new URLSearchParams(window.location.search);
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      setSource({chunk: fragment.get("chunk") ?? query.get("chunk"), quote: fragment.get("quote") ?? query.get("quote")});
    };
    readSource();
    window.addEventListener("hashchange", readSource);
    window.addEventListener("popstate", readSource);
    return () => {
      window.removeEventListener("hashchange", readSource);
      window.removeEventListener("popstate", readSource);
    };
  }, [id]);
  useEffect(() => {
    highlight.current?.scrollIntoView({block: "center"});
  }, [selection.start, selection.end]);
  useEffect(() => {
    const refresh = () => {
      void api<{status: string; error?: string | null}>("/api/embedding-status").then(setModelStatus).catch(() => {});
      void api<DocumentRecord>(`/api/documents/${id}`).then(setDocument).catch(() => {});
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [id]);
  async function extract() {
    if (!document) return;
    setExtracting(true);
    setError("");
    try {
      const policy = await api<PolicyVersion>("/api/policies/propose", {method: "POST", body: JSON.stringify({name: document.filename, document_ids: [id]})});
      router.push(`/policies/${policy.id}`);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setExtracting(false); }
  }
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
      const result = await api<{cleanup_pending?: boolean}>(`/api/documents/${id}`, { method: "DELETE" });
      if (result.cleanup_pending) alert("The record was deleted. Original file cleanup is pending and will retry automatically.");
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
  const canWrite = user?.role === "reviewer" || (user?.role === "analyst" && document.kind === "evidence" && !document.case_is_decided);
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
            {canWrite && (
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
      {document.kind === "policy" && <section className="card card-body" style={{marginBottom: 18}}>
        <h2>Requirements</h2>
        <p>Extract requirements from the full document, then review and approve the saved draft. Reopening saved requirements uses no model API calls.</p>
        {policies.map((policy) => <p key={policy.id}><Link className="arrow-link" href={`/policies/${policy.id}`}>{policy.name} · v{policy.version} · {policy.status} · {policy.requirements.length} requirements</Link></p>)}
        {user?.role === "reviewer" && <button className="button" disabled={extracting} onClick={extract}>{extracting ? "Extracting requirements…" : "Extract requirements"}</button>}
      </section>}
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
      {selection.notice && <p className="notice notice-info" role="status">{selection.notice}</p>}
      <section className="card">
        <div className="card-header"><h2>Full document</h2></div>
        <div className="card-body source-document" style={{whiteSpace: "pre-wrap"}}>
          {selection.start !== undefined && document.text ? <>
            {document.text.slice(0, selection.start)}
            <mark ref={highlight} className="source-highlight" aria-label="Cited quote">{document.text.slice(selection.start, selection.end)}</mark>
            {document.text.slice(selection.end)}
          </> : document.text ?? "Full document text is unavailable. Download the original to read it."}
        </div>
      </section>
      <details className="card card-body" style={{marginTop: 18}}><summary>Technical details</summary>
        <p aria-live="polite">Semantic index: <strong>{document.index_status ?? "pending"}</strong> · Local model: {modelStatus?.status ?? "checking"}</p>
        {document.index_error && <p>{document.index_error}</p>}
        {modelStatus?.error && <p>{modelStatus.error}</p>}
        <p>Indexing runs in the background. The full source text remains available.</p>
        {canWrite && <button className="button button-small button-secondary" disabled={indexing} onClick={reindex}>{indexing ? "Queuing…" : "Reindex document"}</button>}
      </details>
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
