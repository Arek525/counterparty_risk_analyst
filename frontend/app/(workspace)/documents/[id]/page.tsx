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
  }, [document]);
  async function remove() {
    if (
      !confirm(
        "Usunąć ten dokument? Dokumentu powiązanego z zachowaną wersją nie można usunąć.",
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
  if (!document && !error) return <Spinner label="Ładowanie źródła…" />;
  if (!document) return <ErrorNotice message={error} retry={load} />;
  return (
    <>
      <PageHeader
        eyebrow={
          document.kind === "policy" ? "Dokument polityki" : "Dowód kontrahenta"
        }
        title={document.filename}
        description={`Wersja ${document.version} · ${formatDate(document.created_at)}`}
        actions={
          <>
            <a
              className="button button-secondary"
              href={`/api/documents/${document.id}/download`}
            >
              Pobierz oryginał
            </a>
            {user?.role !== "auditor" && (
              <button
                className="button button-danger"
                disabled={deleting}
                onClick={remove}
              >
                {deleting ? "Usuwanie…" : "Usuń"}
              </button>
            )}
          </>
        }
      />
      {error && <ErrorNotice message={error} />}
      {document.kind === "evidence" && (
        <div className="notice notice-info" style={{ marginBottom: 18 }}>
          <p>
            <strong>Rodzaj źródła:</strong>{" "}
            {document.evidence_type === "independent"
              ? "niezależny dowód"
              : "deklaracja kontrahenta"}
          </p>
        </div>
      )}
      <section className="card">
        <div className="card-header">
          <h2>Wyodrębniony tekst źródłowy</h2>
          <StatusBadge value="neutral">
            {document.chunks?.length ?? 0} fragmentów
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
              Dokument nie zawiera fragmentów tekstowych.
            </p>
          )}
        </div>
      </section>
      <p style={{ marginTop: 18 }}>
        <Link
          className="arrow-link"
          href={document.case_id ? `/cases/${document.case_id}` : "/policies"}
        >
          ← Powrót
        </Link>
      </p>
    </>
  );
}
