"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
import type {
  AnalysisRun,
  AssessmentCase,
  DocumentRecord,
  PolicyVersion,
  Relationship,
} from "@/lib/types";

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canWrite = user?.role !== "auditor";
  const [caseItem, setCaseItem] = useState<AssessmentCase | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [policies, setPolicies] = useState<PolicyVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<"edit" | "analysis" | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [evidenceType, setEvidenceType] = useState<
    "declaration" | "independent"
  >("declaration");
  const [uploading, setUploading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      api<AssessmentCase>(`/api/cases/${id}`),
      api<DocumentRecord[]>(`/api/documents?case_id=${encodeURIComponent(id)}`),
      api<AnalysisRun[]>(`/api/cases/${id}/runs`),
      api<PolicyVersion[]>("/api/policies"),
    ]);
    if (results[0].status === "fulfilled") setCaseItem(results[0].value);
    else setError(errorMessage(results[0].reason));
    if (results[1].status === "fulfilled") setDocuments(results[1].value);
    if (results[2].status === "fulfilled") setRuns(results[2].value);
    if (results[3].status === "fulfilled") setPolicies(results[3].value);
    setLoading(false);
  }
  useEffect(() => {
    void load();
  }, [id]);

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    data.append("kind", "evidence");
    data.append("case_id", id);
    data.append("evidence_type", evidenceType);
    try {
      await api<DocumentRecord>("/api/documents", {
        method: "POST",
        body: data,
      });
      setFile(null);
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setUploading(false);
    }
  }

  if (loading) return <Spinner label="Ładowanie sprawy…" />;
  if (!caseItem)
    return (
      <ErrorNotice message={error || "Nie znaleziono sprawy."} retry={load} />
    );
  const latestRun = runs[0];

  return (
    <>
      <PageHeader
        eyebrow={caseItem.counterparty_name}
        title={caseItem.name}
        description={`Utworzono ${formatDate(caseItem.created_at)}`}
        actions={
          <>
            <Link className="button button-quiet" href={`/audit?case_id=${id}`}>
              Historia
            </Link>
            {canWrite && (
              <button className="button" onClick={() => setModal("analysis")}>
                Uruchom analizę
              </button>
            )}
          </>
        }
      />
      {error && <ErrorNotice message={error} />}
      <div className="detail-grid">
        <div className="stack">
          <section className="card">
            <div className="card-header">
              <h2>Dokumenty dowodowe</h2>
              {canWrite && (
                <span className="subtle">PDF, Markdown lub TXT</span>
              )}
            </div>
            <div className="card-body">
              {documents.length === 0 ? (
                <EmptyState
                  title="Brak dokumentów"
                  description="Dodaj kwestionariusz, umowę, certyfikat lub politykę kontrahenta."
                />
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
                      <span className="subtle">
                        {document.evidence_type === "independent"
                          ? "Niezależny dowód"
                          : "Deklaracja kontrahenta"}{" "}
                        · wersja {document.version} ·{" "}
                        {formatDate(document.created_at)}
                      </span>
                    </div>
                    <Link
                      className="arrow-link"
                      href={`/documents/${document.id}`}
                    >
                      Źródło <Icon name="arrow" />
                    </Link>
                  </div>
                ))
              )}
              {canWrite && (
                <form className="upload-zone" onSubmit={upload}>
                  <Icon name="upload" style={{ width: 25, marginBottom: 7 }} />
                  <div>
                    <input
                      aria-label="Dokument dowodowy"
                      type="file"
                      accept=".pdf,.md,.txt,text/plain,text/markdown,application/pdf"
                      onChange={(event) =>
                        setFile(event.target.files?.[0] ?? null)
                      }
                    />
                  </div>
                  <label
                    className="field"
                    style={{
                      maxWidth: 340,
                      margin: "12px auto 0",
                      textAlign: "left",
                    }}
                  >
                    <span>Rodzaj dowodu</span>
                    <select
                      className="select"
                      value={evidenceType}
                      onChange={(event) =>
                        setEvidenceType(
                          event.target.value as "declaration" | "independent",
                        )
                      }
                    >
                      <option value="declaration">
                        Deklaracja kontrahenta
                      </option>
                      <option value="independent">Niezależny dowód</option>
                    </select>
                    <small className="field-help">
                      Deklaracja opisuje stanowisko kontrahenta; niezależny
                      dowód pochodzi z osobnego źródła.
                    </small>
                  </label>
                  <button
                    className="button button-small"
                    style={{ marginTop: 12 }}
                    disabled={!file || uploading}
                  >
                    {uploading ? "Przesyłanie…" : "Dodaj dokument"}
                  </button>
                </form>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Analizy</h2>
              <span className="subtle">Najnowsze jako pierwsze</span>
            </div>
            {runs.length === 0 ? (
              <EmptyState
                title="Brak analiz"
                description="Połącz sprawę z zatwierdzoną polityką i uruchom ocenę."
                action={
                  canWrite && (
                    <button
                      className="button"
                      onClick={() => setModal("analysis")}
                    >
                      Uruchom pierwszą analizę
                    </button>
                  )
                }
              />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Wariant</th>
                      <th>Model</th>
                      <th>Utworzono</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.id}>
                        <td>
                          <StatusBadge value={run.status}>
                            {statusLabels[run.status] ?? run.status}
                          </StatusBadge>
                        </td>
                        <td>
                          {run.retrieval_variant === "hybrid"
                            ? "Hybrydowy"
                            : "Leksykalny"}
                        </td>
                        <td className="subtle">{run.model_mode}</td>
                        <td className="subtle">{formatDate(run.created_at)}</td>
                        <td>
                          <Link
                            className="arrow-link"
                            aria-label={`Otwórz analizę ${formatDate(run.created_at)}`}
                            href={`/runs/${run.id}`}
                          >
                            Otwórz <Icon name="arrow" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <aside className="stack">
          <section className="card">
            <div className="card-header">
              <h2>Kontekst relacji</h2>
              {canWrite && (
                <button
                  className="button button-small button-quiet"
                  onClick={() => setModal("edit")}
                >
                  Edytuj
                </button>
              )}
            </div>
            <div className="card-body">
              <dl className="definition-list">
                <div>
                  <dt>Cel</dt>
                  <dd>{caseItem.relationship.purpose}</dd>
                </div>
                <div>
                  <dt>Udostępniane dane</dt>
                  <dd>{caseItem.relationship.data_shared}</dd>
                </div>
                <div>
                  <dt>Dostęp do systemów</dt>
                  <dd>{caseItem.relationship.system_access}</dd>
                </div>
                <div>
                  <dt>Krytyczność</dt>
                  <dd>
                    <StatusBadge
                      value={
                        caseItem.relationship.business_criticality === "high"
                          ? "High"
                          : caseItem.relationship.business_criticality ===
                              "medium"
                            ? "Medium"
                            : "Low"
                      }
                    >
                      {caseItem.relationship.business_criticality}
                    </StatusBadge>
                  </dd>
                </div>
                <div>
                  <dt>Dane osobowe</dt>
                  <dd>{caseItem.relationship.personal_data ? "Tak" : "Nie"}</dd>
                </div>
                <div>
                  <dt>Dostęp uprzywilejowany</dt>
                  <dd>
                    {caseItem.relationship.privileged_access ? "Tak" : "Nie"}
                  </dd>
                </div>
              </dl>
            </div>
          </section>
          {latestRun && (
            <section className="card">
              <div className="card-header">
                <h2>Ostatnia ocena</h2>
              </div>
              <div className="card-body">
                <StatusBadge value={latestRun.status}>
                  {statusLabels[latestRun.status]}
                </StatusBadge>
                <p className="subtle">
                  Wersja polityki jest związana z tym przebiegiem i pozostaje
                  niezmienna.
                </p>
                <Link className="arrow-link" href={`/runs/${latestRun.id}`}>
                  Przejdź do raportu <Icon name="arrow" />
                </Link>
              </div>
            </section>
          )}
        </aside>
      </div>
      {modal === "edit" && (
        <EditCaseModal
          item={caseItem}
          close={() => setModal(null)}
          saved={async () => {
            setModal(null);
            await load();
          }}
        />
      )}
      {modal === "analysis" && (
        <StartRunModal
          caseId={id}
          policies={policies.filter((policy) => policy.status === "approved")}
          close={() => setModal(null)}
          created={(run) => router.push(`/runs/${run.id}`)}
        />
      )}
    </>
  );
}

function EditCaseModal({
  item,
  close,
  saved,
}: {
  item: AssessmentCase;
  close: () => void;
  saved: () => Promise<void>;
}) {
  const [name, setName] = useState(item.name);
  const [relationship, setRelationship] = useState<Relationship>(
    item.relationship,
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const set = <K extends keyof Relationship>(key: K, value: Relationship[K]) =>
    setRelationship((current) => ({ ...current, [key]: value }));
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await api(`/api/cases/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, relationship }),
      });
      await saved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Edytuj kontekst relacji" close={close}>
      <form className="modal-content" onSubmit={submit}>
        {error && <ErrorNotice message={error} />}
        <label className="field">
          <span>Nazwa sprawy</span>
          <input
            className="input"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Cel współpracy</span>
          <textarea
            className="textarea"
            required
            value={relationship.purpose}
            onChange={(e) => set("purpose", e.target.value)}
          />
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Udostępniane dane</span>
            <textarea
              className="textarea"
              required
              value={relationship.data_shared}
              onChange={(e) => set("data_shared", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Dostęp do systemów</span>
            <textarea
              className="textarea"
              required
              value={relationship.system_access}
              onChange={(e) => set("system_access", e.target.value)}
            />
          </label>
        </div>
        <label className="field">
          <span>Krytyczność</span>
          <select
            className="select"
            value={relationship.business_criticality}
            onChange={(e) => set("business_criticality", e.target.value)}
          >
            <option value="low">Niska</option>
            <option value="medium">Średnia</option>
            <option value="high">Wysoka</option>
          </select>
        </label>
        <div className="form-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={relationship.personal_data}
              onChange={(e) => set("personal_data", e.target.checked)}
            />
            Dane osobowe
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={relationship.privileged_access}
              onChange={(e) => set("privileged_access", e.target.checked)}
            />
            Dostęp uprzywilejowany
          </label>
        </div>
        <div className="form-actions">
          <button type="button" className="button button-quiet" onClick={close}>
            Anuluj
          </button>
          <button className="button" disabled={pending}>
            {pending ? "Zapisywanie…" : "Zapisz zmiany"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function StartRunModal({
  caseId,
  policies,
  close,
  created,
}: {
  caseId: string;
  policies: PolicyVersion[];
  close: () => void;
  created: (run: AnalysisRun) => void;
}) {
  const [policyId, setPolicyId] = useState(policies[0]?.id ?? "");
  const [variant, setVariant] = useState<"lexical" | "hybrid">("hybrid");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      created(
        await api<AnalysisRun>(`/api/cases/${caseId}/runs`, {
          method: "POST",
          body: JSON.stringify({
            policy_version_id: policyId,
            retrieval_variant: variant,
          }),
        }),
      );
    } catch (reason) {
      setError(errorMessage(reason));
      setPending(false);
    }
  }
  return (
    <Modal title="Uruchom analizę" close={close}>
      <form className="modal-content" onSubmit={submit}>
        {error && <ErrorNotice message={error} />}{" "}
        {policies.length === 0 ? (
          <EmptyState
            title="Brak zatwierdzonej polityki"
            description="Recenzent musi najpierw zatwierdzić co najmniej jeden zestaw wymagań."
            action={
              <Link href="/policies" className="button">
                Przejdź do polityk
              </Link>
            }
          />
        ) : (
          <>
            <label className="field">
              <span>Zatwierdzona polityka</span>
              <select
                className="select"
                value={policyId}
                onChange={(e) => setPolicyId(e.target.value)}
              >
                {policies.map((policy) => (
                  <option key={policy.id} value={policy.id}>
                    {policy.name} · v{policy.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Wariant wyszukiwania dowodów</span>
              <select
                className="select"
                value={variant}
                onChange={(e) =>
                  setVariant(e.target.value as "lexical" | "hybrid")
                }
              >
                <option value="hybrid">
                  Hybrydowy — słowa kluczowe i podobieństwo
                </option>
                <option value="lexical">Leksykalny — słowa kluczowe</option>
              </select>
              <small className="field-help">
                Wariant jest zapisywany przy przebiegu, aby umożliwić porównanie
                wyników.
              </small>
            </label>
            <div className="notice notice-info">
              <div>
                <strong>Niezmienny zapis wejścia</strong>
                <p>
                  Analiza zapisze wersje sprawy, dokumentów i polityki użyte do
                  oceny.
                </p>
              </div>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="button button-quiet"
                onClick={close}
              >
                Anuluj
              </button>
              <button className="button" disabled={pending || !policyId}>
                {pending ? "Uruchamianie…" : "Uruchom analizę"}
              </button>
            </div>
          </>
        )}
      </form>
    </Modal>
  );
}
