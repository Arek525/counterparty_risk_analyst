"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import {
  EmptyState,
  ErrorNotice,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { formatDate, statusLabels } from "@/lib/format";
import type { DocumentRecord, PolicyVersion } from "@/lib/types";

export default function PoliciesPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "auditor";
  const [policies, setPolicies] = useState<PolicyVersion[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    const [policyResult, documentResult] = await Promise.allSettled([
      api<PolicyVersion[]>("/api/policies"),
      api<DocumentRecord[]>("/api/documents"),
    ]);
    if (policyResult.status === "fulfilled") setPolicies(policyResult.value);
    else setError(errorMessage(policyResult.reason));
    if (documentResult.status === "fulfilled")
      setDocuments(
        documentResult.value.filter((document) => document.kind === "policy"),
      );
    setLoading(false);
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (!documents.some((doc) => ["pending", "indexing"].includes(doc.index_status ?? ""))) return;
    const timer = setInterval(() => {
      void api<DocumentRecord[]>("/api/documents").then(setDocuments).catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [documents]);
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    data.append("kind", "policy");
    try {
      await api("/api/documents", { method: "POST", body: data });
      setFile(null);
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Criteria source"
        title="Policies and requirements"
        description="Requirements are derived from source documents, and every approved version remains immutable."
        actions={
          canWrite && (
            <button className="button" onClick={() => setCreateOpen(true)}>
              <Icon name="plus" />
              New policy set
            </button>
          )
        }
      />
      {error && <ErrorNotice message={error} retry={load} />}
      <div className="detail-grid">
        <section className="card">
          <div className="card-header">
            <h2>Policy sets</h2>
            <span className="subtle">{policies.length} versions</span>
          </div>
          {loading ? (
            <Spinner label="Loading policies…" />
          ) : policies.length === 0 ? (
            <EmptyState
              title="No policy sets"
              description="Upload a policy document and generate proposed requirements."
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Status</th>
                    <th>Requirements</th>
                    <th>Date</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {policies.map((policy) => (
                    <tr key={policy.id}>
                      <td>
                        <strong>{policy.name}</strong>
                      </td>
                      <td>v{policy.version}</td>
                      <td>
                        <StatusBadge value={policy.status}>
                          {statusLabels[policy.status]}
                        </StatusBadge>
                      </td>
                      <td>{policy.requirements?.length ?? 0}</td>
                      <td className="subtle">
                        {formatDate(policy.approved_at ?? policy.created_at)}
                      </td>
                      <td>
                        <Link
                          href={`/policies/${policy.id}`}
                          className="arrow-link"
                        >
                          Open <Icon name="arrow" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <aside className="card">
          <div className="card-header">
            <h2>Source documents</h2>
          </div>
          <div className="card-body">
            {documents.length === 0 ? (
              <p className="subtle">
                No policy document has been uploaded yet.
              </p>
            ) : (
              documents.map((document) => (
                <div className="document-row" key={document.id}>
                  <span className="file-mark">
                    {document.filename.split(".").pop()?.toUpperCase()}
                  </span>
                  <div className="document-row-main">
                    <Link href={`/documents/${document.id}`}>
                      <strong>{document.filename}</strong>
                    </Link>
                      <span className="subtle">Semantic index: {document.index_status ?? "pending"}</span>
                    <span className="subtle">version {document.version}</span>
                  </div>
                </div>
              ))
            )}
            {canWrite && (
              <form className="upload-zone" onSubmit={upload}>
                <Icon name="upload" style={{ width: 24 }} />
                <div>
                  <input
                    aria-label="Policy document"
                    type="file"
                    accept=".pdf,.md,.txt,text/plain,text/markdown,application/pdf"
                    onChange={(event) =>
                      setFile(event.target.files?.[0] ?? null)
                    }
                  />
                </div>
                <button
                  className="button button-small"
                  style={{ marginTop: 12 }}
                  disabled={!file || uploading}
                >
                  {uploading ? "Uploading…" : "Add document"}
                </button>
              </form>
            )}
          </div>
        </aside>
      </div>
      {createOpen && (
        <ProposePolicyModal
          documents={documents}
          close={() => setCreateOpen(false)}
          created={(policy) => {
            setCreateOpen(false);
            location.assign(`/policies/${policy.id}`);
          }}
        />
      )}
    </>
  );
}

function ProposePolicyModal({
  documents,
  close,
  created,
}: {
  documents: DocumentRecord[];
  close: () => void;
  created: (policy: PolicyVersion) => void;
}) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : [...current, id],
    );
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      created(
        await api<PolicyVersion>("/api/policies/propose", {
          method: "POST",
          body: JSON.stringify({ name, document_ids: selected }),
        }),
      );
    } catch (reason) {
      setError(errorMessage(reason));
      setPending(false);
    }
  }
  return (
    <Modal title="Propose requirements" close={close}>
      <form className="modal-content" onSubmit={submit}>
        {error && <ErrorNotice message={error} />}
        <label className="field">
          <span>Policy set name</span>
          <input
            className="input"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Minimum supplier requirements"
          />
        </label>
        <span className="field-label">Source documents</span>
        <div className="stack" style={{ gap: 8, marginTop: 8 }}>
          {documents.length === 0 ? (
            <div className="notice notice-info">
              <p>Add a policy document first.</p>
            </div>
          ) : (
            documents.map((document) => (
              <label className="demo-account" key={document.id}>
                <div>
                  <strong>{document.filename}</strong>
                  <span>version {document.version}</span>
                </div>
                <input
                  type="checkbox"
                  checked={selected.includes(document.id)}
                  onChange={() => toggle(document.id)}
                />
              </label>
            ))
          )}
        </div>
        <p className="field-help">
          The adapter will propose requirements with citations. Before approval,
          you can revise them.
        </p>
        <div className="form-actions">
          <button type="button" className="button button-quiet" onClick={close}>
            Cancel
          </button>
          <button
            className="button"
            disabled={pending || !name || selected.length === 0}
          >
            {pending ? "Generating proposals…" : "Create draft"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
