"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  findingLabels,
  formatDate,
  formatLocation,
  statusLabels,
  titleCase,
} from "@/lib/format";
import type {
  AnalysisRun,
  ApprovalRequest,
  Citation,
  Decision,
  DocumentRecord,
  Report,
} from "@/lib/types";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [tickets, setTickets] = useState<ApprovalRequest[]>([]);
  const [error, setError] = useState("");
  const [source, setSource] = useState<Citation | null>(null);
  const load = useCallback(async () => {
    try {
      const [runValue, ticketValue] = await Promise.all([
        api<AnalysisRun>(`/api/runs/${id}`),
        api<ApprovalRequest[]>(`/api/runs/${id}/tickets`),
      ]);
      setRun(runValue);
      setTickets(ticketValue);
      setError("");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!run || !(run.status === "queued" || run.status === "running")) return;
    const timer = setInterval(() => void load(), 1800);
    return () => clearInterval(timer);
  }, [load, run]);
  const decision = useMemo<Decision | null>(
    () => run?.decision ?? run?.decisions?.[0] ?? null,
    [run],
  );
  if (!run && !error) return <Spinner label="Ładowanie analizy…" />;
  if (!run) return <ErrorNotice message={error} retry={load} />;
  const processing = run.status === "queued" || run.status === "running";
  return (
    <>
      <PageHeader
        eyebrow={`Analiza · ${run.retrieval_variant}`}
        title="Raport oceny"
        description={`Przebieg ${run.id}`}
        actions={
          <Link className="button button-quiet" href={`/cases/${run.case_id}`}>
            Powrót do sprawy
          </Link>
        }
      />
      {error && <ErrorNotice message={error} />}
      <RunProgress run={run} />
      {processing && (
        <section className="card">
          <Spinner
            label={
              run.status === "queued"
                ? "Analiza czeka na wolnego pracownika…"
                : "Trwa wyszukiwanie dowodów i ocena wymagań…"
            }
          />
        </section>
      )}
      {run.status === "failed" && (
        <ErrorNotice message={run.error || "Analiza zakończyła się błędem."} />
      )}{" "}
      {run.report && (
        <>
          {run.report.workflow_error && (
            <div style={{ marginBottom: 18 }}>
              <ErrorNotice message={run.report.workflow_error} />
            </div>
          )}
          <div className="stat-grid">
            <article className="card stat">
              <span className="stat-label">Ryzyko</span>
              <span className="stat-value">
                <StatusBadge value={run.report.risk}>
                  {run.report.risk}
                </StatusBadge>
              </span>
            </article>
            <article className="card stat">
              <span className="stat-label">Kompletność dowodów</span>
              <span className="stat-value">{run.report.completeness}%</span>
              <div className="progress-track">
                <div
                  className="progress-value"
                  style={{ width: `${run.report.completeness}%` }}
                />
              </div>
            </article>
            <article className="card stat">
              <span className="stat-label">Decyzja człowieka</span>
              <span className="stat-value" style={{ fontSize: 18 }}>
                {decision ? (
                  <StatusBadge value={decision.decision}>
                    {statusLabels[decision.decision]}
                  </StatusBadge>
                ) : (
                  <StatusBadge value="awaiting_review">
                    Oczekuje na decyzję
                  </StatusBadge>
                )}
              </span>
            </article>
          </div>
          <section className="card report-summary">
            <h2>Podsumowanie</h2>
            <p>{run.report.summary}</p>
          </section>
          <div className="detail-grid" style={{ marginTop: 18 }}>
            <div className="stack">
              <section>
                <h2 style={{ font: "600 24px Georgia,serif" }}>
                  Ustalenia ({run.report.findings.length})
                </h2>
                <div className="stack">
                  {run.report.findings.map((finding) => (
                    <article
                      className="card finding"
                      key={finding.requirement_id}
                    >
                      <div className="finding-header">
                        <div>
                          <StatusBadge value={finding.status}>
                            {findingLabels[finding.status]}
                          </StatusBadge>
                          <h3>{finding.title}</h3>
                        </div>
                        <StatusBadge value={finding.severity}>
                          {finding.severity}
                        </StatusBadge>
                      </div>
                      <div className="finding-body">
                        <p>{finding.explanation}</p>
                      {(typeof finding.missing_information === "string"
                        ? finding.missing_information.trim().length > 0
                        : (finding.missing_information?.length ?? 0) > 0) && (
                          <div className="notice notice-info">
                            <p>
                              <strong>Brakująca informacja:</strong>{" "}
                              {Array.isArray(finding.missing_information)
                                ? finding.missing_information.join(" ")
                                : finding.missing_information}
                            </p>
                          </div>
                        )}
                        {finding.evidence.map((evidence) => (
                          <button
                            className="evidence-quote"
                            key={`${evidence.chunk_id}-${evidence.quote}`}
                            onClick={() => setSource(evidence)}
                          >
                            <q>{evidence.quote}</q>
                            <span>
                              <Icon
                                name="source"
                                style={{ width: 14, verticalAlign: "middle" }}
                              />{" "}
                              {evidence.evidence_type === "independent"
                                ? "niezależny dowód"
                                : "deklaracja"}{" "}
                              · {formatLocation(evidence.location)} · otwórz
                              źródło
                            </span>
                          </button>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
              <ReportLists
                questions={run.report.questions}
                discrepancies={run.report.discrepancies}
              />
            </div>
            <aside className="stack">
              <DecisionPanel
                run={run}
                decision={decision}
                canDecide={
                  user?.role === "reviewer" || user?.role === "administrator"
                }
                saved={load}
              />
              <TicketPanel run={run} tickets={tickets} saved={load} />
              <section className="card">
                <div className="card-header">
                  <h2>Ślad wykonania</h2>
                </div>
                <div className="card-body">
                  <dl className="definition-list">
                    <div>
                      <dt>Model</dt>
                      <dd>
                        {run.report.model_name}{" "}
                        <StatusBadge value="neutral">
                          {run.report.model_mode}
                        </StatusBadge>
                      </dd>
                    </div>
                    <div>
                      <dt>Reguły</dt>
                      <dd className="mono">{run.report.rules_version}</dd>
                    </div>
                    <div>
                      <dt>Prompt</dt>
                      <dd className="mono">{run.report.prompt_version}</dd>
                    </div>
                    <div>
                      <dt>Czas</dt>
                      <dd>{run.report.metrics.duration_ms} ms</dd>
                    </div>
                    <div>
                      <dt>Tokeny</dt>
                      <dd>
                        {run.report.metrics.input_tokens} /{" "}
                        {run.report.metrics.output_tokens}
                      </dd>
                    </div>
                    <div>
                      <dt>Koszt</dt>
                      <dd>
                        {run.report.metrics.cost_usd === null
                          ? "Koszt nieustalony"
                          : `$${run.report.metrics.cost_usd.toFixed(4)}`}
                      </dd>
                    </div>
                  </dl>
                </div>
              </section>
            </aside>
          </div>
        </>
      )}
      {source && (
        <SourceModal citation={source} close={() => setSource(null)} />
      )}
    </>
  );
}

function RunProgress({ run }: { run: AnalysisRun }) {
  const steps = [
    { key: "queued", label: "Utworzono" },
    { key: "running", label: "Analiza" },
    { key: "awaiting_review", label: "Przegląd" },
    { key: "completed", label: "Decyzja" },
  ];
  const index =
    run.status === "failed"
      ? 1
      : steps.findIndex((entry) => entry.key === run.status);
  return (
    <section className="card" style={{ marginBottom: 18 }}>
      <div className="card-body">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          {steps.map((step, i) => (
            <div
              key={step.key}
              style={{ flex: 1, textAlign: "center", position: "relative" }}
            >
              <span
                className={`badge ${i <= index ? "badge-success" : "badge-neutral"}`}
              >
                {i < index ? "✓ " : ""}
                {step.label}
              </span>
              {i < steps.length - 1 && (
                <span
                  aria-hidden="true"
                  style={{
                    height: 1,
                    background: i < index ? "var(--pine)" : "var(--line)",
                    position: "absolute",
                    top: "50%",
                    left: "65%",
                    right: "-35%",
                    zIndex: -1,
                  }}
                />
              )}
            </div>
          ))}
        </div>
        {run.events && run.events.length > 0 && (
          <p
            className="subtle"
            style={{ textAlign: "center", margin: "14px 0 0" }}
          >
          {run.events.at(-1)?.message ??
            runEventLabel(
              run.events.at(-1)?.event ?? run.events.at(-1)?.type ?? "",
            )}
        </p>
      )}
      </div>
    </section>
  );
}

function runEventLabel(event: string): string {
  const labels: Record<string, string> = {
    "analysis.queued": "Analiza została dodana do kolejki",
    "run.started": "Analiza została rozpoczęta",
    "run.awaiting_review": "Raport oczekuje na przegląd",
    "analysis.decision": "Decyzja została zapisana",
    "run.completed": "Analiza została zakończona",
    "run.retry_scheduled": "Zaplanowano ponowienie analizy",
    "run.failed": "Analiza zakończyła się błędem",
  };
  if (labels[event]) return labels[event];
  if (event.startsWith("run.") || event.startsWith("analysis.")) {
    return "Zaktualizowano stan analizy";
  }
  return titleCase(event);
}

function ReportLists({
  questions,
  discrepancies,
}: {
  questions: string[];
  discrepancies: Report["discrepancies"];
}) {
  if (!questions.length && !discrepancies.length) return null;
  return (
    <div className="split-list">
      {questions.length > 0 && (
        <section className="card">
          <div className="card-header">
            <h2>Pytania uzupełniające</h2>
          </div>
          <div className="card-body">
            <ol className="plain-list">
              {questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ol>
          </div>
        </section>
      )}
      {discrepancies.length > 0 && (
        <section className="card">
          <div className="card-header">
            <h2>Rozbieżności</h2>
          </div>
          <div className="card-body">
            <ul className="plain-list">
              {discrepancies.map((item, index) => {
                const description =
                  typeof item === "string"
                    ? item
                    : (item.description ??
                      item.message ??
                      item.explanation ??
                      "Rozbieżność wymaga wyjaśnienia.");
                return <li key={index}>{description}</li>;
              })}
            </ul>
          </div>
        </section>
      )}
    </div>
  );
}

function DecisionPanel({
  run,
  decision,
  canDecide,
  saved,
}: {
  run: AnalysisRun;
  decision: Decision | null;
  canDecide: boolean;
  saved: () => Promise<void>;
}) {
  const [value, setValue] = useState<Decision["decision"]>("needs_information");
  const [rationale, setRationale] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await api(`/api/runs/${run.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision: value, rationale }),
      });
      await saved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="card">
      <div className="card-header">
        <h2>Decyzja</h2>
      </div>
      <div className="card-body">
        {decision ? (
          <>
            <StatusBadge value={decision.decision}>
              {statusLabels[decision.decision]}
            </StatusBadge>
            <p>{decision.rationale}</p>
            <span className="subtle">{formatDate(decision.created_at)}</span>
          </>
        ) : run.status !== "awaiting_review" ? (
          <p className="subtle">
            Decyzję można zapisać po przygotowaniu raportu.
          </p>
        ) : !canDecide ? (
          <p className="subtle">Raport oczekuje na decyzję recenzenta.</p>
        ) : (
          <form onSubmit={submit}>
            {error && <ErrorNotice message={error} />}
            <div className="decision-options">
              {(
                [
                  ["accepted", "Akceptuję"],
                  ["rejected", "Odrzucam"],
                  ["needs_information", "Potrzebuję danych"],
                ] as const
              ).map(([key, label]) => (
                <button
                  type="button"
                  key={key}
                  className={`decision-option ${value === key ? "selected" : ""}`}
                  onClick={() => setValue(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="field">
              <span>Uzasadnienie decyzji</span>
              <textarea
                className="textarea"
                required
                minLength={3}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Wyjaśnij, które ustalenia wpłynęły na decyzję."
              />
            </label>
            <button
              className="button"
              style={{ width: "100%" }}
              disabled={pending || !rationale.trim()}
            >
              {pending ? "Zapisywanie…" : "Zapisz decyzję"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

function TicketPanel({
  run,
  tickets,
  saved,
}: {
  run: AnalysisRun;
  tickets: ApprovalRequest[];
  saved: () => Promise<void>;
}) {
  const { user } = useAuth();
  const [title, setTitle] = useState(
    `Uzupełnienie informacji — analiza ${run.id.slice(0, 8)}`,
  );
  const [body, setBody] = useState(
    run.report?.questions.map((q) => `- ${q}`).join("\n") ?? "",
  );
  const [preview, setPreview] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [currentStatuses, setCurrentStatuses] = useState<
    Record<string, string>
  >({});
  const canPropose =
    user?.role === "analyst" ||
    user?.role === "reviewer" ||
    user?.role === "administrator";
  async function action(path: string, key: string, payload?: unknown) {
    setPending(key);
    setError("");
    try {
      await api(path, {
        method: "POST",
        body: payload ? JSON.stringify(payload) : undefined,
      });
      await saved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending("");
    }
  }
  async function refresh(approvalId: string) {
    setPending(approvalId);
    setError("");
    try {
      const ticket = await api<{ status?: string }>(
        `/api/approvals/${approvalId}/ticket-status`,
      );
      if (ticket.status) {
        setCurrentStatuses((current) => ({
          ...current,
          [approvalId]: ticket.status as string,
        }));
      }
      await saved();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending("");
    }
  }
  return (
    <section className="card">
      <div className="card-header">
        <h2>Zgłoszenie follow-up</h2>
      </div>
      <div className="card-body">
        {error && <ErrorNotice message={error} />}
        <p className="subtle">
          Propozycja, jej zatwierdzenie i zapis w usłudze to trzy osobne kroki
          audytowe.
        </p>
        {!canPropose ? (
          <p className="subtle">Konto audytora ma dostęp tylko do odczytu.</p>
        ) : (
          <>
            <label className="field">
              <span>Tytuł</span>
              <input
                className="input"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setPreview(false);
                }}
              />
            </label>
            <label className="field">
              <span>Treść</span>
              <textarea
                className="textarea"
                value={body}
                onChange={(e) => {
                  setBody(e.target.value);
                  setPreview(false);
                }}
              />
            </label>
          </>
        )}
        {canPropose && preview ? (
          <div className="ticket-preview">
            <h4>{title}</h4>
            <p>{body}</p>
            <div className="form-actions">
              <button
                className="button button-quiet button-small"
                onClick={() => setPreview(false)}
              >
                Wróć do edycji
              </button>
              <button
                className="button button-small"
                disabled={pending === "new"}
                onClick={() =>
                  action(`/api/runs/${run.id}/ticket-proposals`, "new", {
                    title,
                    body,
                  })
                }
              >
                {pending === "new"
                  ? "Zapisywanie…"
                  : "Zapisz dokładną propozycję"}
              </button>
            </div>
          </div>
        ) : canPropose ? (
          <button
            className="button button-secondary button-small"
            disabled={!title.trim() || !body.trim()}
            onClick={() => setPreview(true)}
          >
            Pokaż podgląd propozycji
          </button>
        ) : null}
        {tickets.length > 0 && (
          <div className="stack" style={{ marginTop: 18 }}>
            {tickets.map((approval) => (
              <article className="ticket-preview" key={approval.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 10,
                  }}
                >
                  <h4>
                    {approval.arguments?.title ??
                      approval.ticket?.title ??
                      "Zgłoszenie"}
                  </h4>
                  <StatusBadge value={approval.status}>
                    {statusLabels[approval.status] ?? approval.status}
                  </StatusBadge>
                </div>
                <p>{approval.arguments?.body ?? approval.ticket?.body}</p>
                <span className="subtle">
                  Wygasa: {formatDate(approval.expires_at)}
                </span>
                {approval.error && (
                  <div
                    className="notice notice-error"
                    style={{ marginTop: 10 }}
                  >
                    <p>{approval.error}</p>
                  </div>
                )}
                {approval.ticket && (
                  <p className="subtle">
                    Ticket {approval.ticket.id} · {approval.ticket.service} ·{" "}
                    {currentStatuses[approval.id] ?? approval.ticket.status}
                  </p>
                )}
                <div className="form-actions">
                  {approval.status === "proposed" &&
                    (user?.role === "reviewer" ||
                      user?.role === "administrator") && (
                      <button
                        className="button button-small"
                        disabled={!!pending}
                        onClick={() =>
                          action(
                            `/api/approvals/${approval.id}/approve`,
                            approval.id,
                          )
                        }
                      >
                        Zatwierdź dokładne dane
                      </button>
                    )}
                  {approval.status === "approved" &&
                    approval.approved_by === user?.id && (
                      <button
                        className="button button-small"
                        disabled={!!pending}
                        onClick={() =>
                          action(
                            `/api/approvals/${approval.id}/execute`,
                            approval.id,
                          )
                        }
                      >
                        Wykonaj zapis
                      </button>
                    )}
                  {approval.status === "failed" &&
                    approval.approved_by === user?.id && (
                      <button
                        className="button button-small"
                        disabled={!!pending}
                        onClick={() =>
                          action(
                            `/api/approvals/${approval.id}/reconcile`,
                            approval.id,
                          )
                        }
                      >
                        Odzyskaj potwierdzenie
                      </button>
                    )}
                  {(approval.status === "executed" || approval.ticket) && (
                    <button
                      className="button button-quiet button-small"
                      disabled={!!pending}
                      onClick={() => refresh(approval.id)}
                    >
                      Odśwież status
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SourceModal({
  citation,
  close,
}: {
  citation: Citation;
  close: () => void;
}) {
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<DocumentRecord>(`/api/documents/${citation.document_id}`)
      .then(setDocument)
      .catch((reason) => setError(errorMessage(reason)));
  }, [citation.document_id]);
  const chunk = document?.chunks?.find((item) => item.id === citation.chunk_id);
  return (
    <Modal title="Źródło dowodu" close={close}>
      <div className="modal-content">
        {error && <ErrorNotice message={error} />}{" "}
        {!document && !error && <Spinner label="Pobieranie dokumentu…" />}
        {document && (
          <>
            <p>
              <strong>{document.filename}</strong>
              <br />
              <span className="subtle">
                {formatLocation(citation.location)}
              </span>
            </p>
            <blockquote className="source-document">
              <mark className="source-highlight">{citation.quote}</mark>
              {chunk && chunk.text !== citation.quote && (
                <>
                  <br />
                  <br />
                  {chunk.text}
                </>
              )}
            </blockquote>
            <Link
              className="arrow-link"
              href={`/documents/${citation.document_id}?chunk=${citation.chunk_id}`}
            >
              Otwórz pełny dokument <Icon name="arrow" />
            </Link>
          </>
        )}
      </div>
    </Modal>
  );
}
