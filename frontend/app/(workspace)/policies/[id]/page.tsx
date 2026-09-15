"use client";

import Link from "next/link";
import { DeleteButton } from "@/components/delete-button";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import {
  EmptyState,
  ErrorNotice,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { formatApplicability, formatDate, statusLabels } from "@/lib/format";
import { sourceHref } from "@/lib/source";
import type { DocumentRecord, PolicyVersion, Requirement } from "@/lib/types";

export default function PolicyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [policy, setPolicy] = useState<PolicyVersion | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try {
      const [value, sources] = await Promise.all([
        api<PolicyVersion>(`/api/policies/${id}`),
        api<DocumentRecord[]>("/api/documents"),
      ]);
      setPolicy(value);
      setDocuments(sources);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }
  useEffect(() => {
    void load();
  }, [id]);
  useEffect(() => {
    if (policy?.extraction_status !== "extracting" && (policy?.status !== "approved" || policy.requirement_index_status !== "pending")) return;
    const timer = setInterval(() => void load(), 2500);
    return () => clearInterval(timer);
  }, [policy?.status, policy?.requirement_index_status, policy?.extraction_status, id]);
  async function regenerate() {
    if (!policy || !confirm("Regenerate requirements from all source documents? This makes new model API calls and creates a new draft. Saved versions remain available.")) return;
    setPending(true);
    setError("");
    try {
      const value = await api<PolicyVersion>("/api/policies/propose", { method: "POST", body: JSON.stringify({name: policy.name, document_ids: policy.document_ids, regenerate: true}) });
      router.push(`/policies/${value.id}`);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setPending(false); }
  }
  async function approve() {
    setPending(true);
    setError("");
    try {
      await api(`/api/policies/${id}/approve`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }
  if (!policy && !error) return <Spinner label="Loading policy…" />;
  if (!policy) return <ErrorNotice message={error} retry={load} />;
  const extractionReady = !policy.extraction_status || policy.extraction_status === "ready";
  const requirements = policy.requirements ?? [];
  const canApprove =
    extractionReady && policy.status === "draft" &&
    (user?.role === "reviewer" || user?.role === "administrator");
  return (
    <>
      <PageHeader
        eyebrow={`Version ${policy.version}`}
        title={policy.name}
        description={`Created ${formatDate(policy.created_at)}`}
        actions={
          <>
            <DeleteButton endpoint={`/api/policies/${id}`} label="Delete policy set" redirect="/policies"
              confirmation={`Permanently delete “${policy.name}” v${policy.version}, its requirements and their embeddings? Source documents remain. Referencing reports must be deleted first.`} />
            <StatusBadge value={policy.status}>
              {statusLabels[policy.status]}
            </StatusBadge>
            {user?.role !== "auditor" && <button className="button button-quiet" disabled={pending} onClick={regenerate}>Regenerate requirements</button>}
            {canApprove && (
              <button className="button" onClick={approve} disabled={pending}>
                <Icon name="check" />
                Approve version
              </button>
            )}
          </>
        }
      />
      {error && <ErrorNotice message={error} />}
      <div className="notice notice-info" style={{ marginBottom: 18 }}>
        <div>
          <strong>
            {policy.status === "approved"
              ? "Immutable approved version"
              : "Version requires review"}
          </strong>
          <p>
            {policy.status === "approved"
              ? "Analyses reference this exact version. To change the rules, upload a revised source document and extract a new set."
              : "Review the extracted requirements against their sources before approval. If extraction is incorrect, regenerate or delete this draft. Requirements cannot be edited manually."}
          </p>
        </div>
      </div>
      {policy.extraction_status === "extracting" && <Spinner label="Extracting requirements from the full source documents…" />}
      {policy.extraction_status === "error" && <ErrorNotice message={policy.extraction_error ?? "Extraction failed. Regenerate requirements to try again."} />}
      {policy.status === "draft" && extractionReady && requirements.length > 0 && (
        <details className="card card-body" style={{marginBottom: 18}}>
          <summary>Review full extracted wording</summary>
          <p className="subtle">This is the exact requirement text used in analysis. It is read-only.</p>
          {requirements.map((requirement) => (
            <div key={requirement.id}>
              <h3>{requirement.title}</h3>
              <p>{requirement.description ?? requirement.source.quote}</p>
              <Link className="arrow-link" href={sourceHref(requirement.source)}>View quoted passage <Icon name="arrow" /></Link>
            </div>
          ))}
        </details>
      )}
      {policy.status === "approved" && policy.requirement_index_status && policy.requirement_index_status !== "ready" && (
        <div className="notice notice-info" style={{marginBottom: 18}} aria-live="polite"><p>{policy.requirement_index_status === "error" ? "Requirement preparation failed. " + (policy.requirement_index_error ?? "") : "Preparing approved requirements for analysis in the background…"}</p></div>
      )}
      {requirements.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No requirements"
            description="The adapter proposed no requirements for the selected sources."
          />
        </div>
      ) : (
        <div className="requirements">
          <p className="subtle">
            Requirement IDs identify individual rules, not scores or risk levels.
            In the Northstar sample policies, SEC means Information Security,
            PRI means Privacy, GOV means Supplier Governance, and IR means Incident Response.
            The number identifies a rule within that group. Other policies may use different IDs.
          </p>
          {requirements.map((requirement) => (
            <RequirementCard key={requirement.id} requirement={requirement}
              document={documents.find((document) => document.id === requirement.source.document_id)} />
          ))}
        </div>
      )}
    </>
  );
}

function RequirementCard({ requirement, document }: { requirement: Requirement; document?: DocumentRecord }) {
  return (
    <article className="card requirement">
      <div className="requirement-head">
        <div>
          <h3>{requirement.title}</h3>
          <span className="subtle">Requirement ID: <span className="mono">{requirement.id}</span></span>
        </div>
        <StatusBadge value={requirement.severity}>
          {requirement.severity}
        </StatusBadge>
      </div>
      <div className="requirement-scope">
        <span className="requirement-label">Applies when</span>
        <p>{requirement.applicability_text ?? formatApplicability(requirement.applicability)}</p>
      </div>
      <div className="source-box">
        <small>
          <Link
            className="arrow-link"
            href={sourceHref(requirement.source)}
          >
            {document ? `${document.filename} · v${document.version}` : "Source document unavailable"} · View quoted passage{" "}
            <Icon name="arrow" />
          </Link>
        </small>
      </div>
    </article>
  );
}
