"use client";

import Link from "next/link";
import { DeleteButton } from "@/components/delete-button";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import {
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
  statusLabels,
  titleCase,
} from "@/lib/format";
import { sourceHref } from "@/lib/source";
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
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [retrying, setRetrying] = useState(false);
  const [sourceError, setSourceError] = useState("");
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
    if (!run?.case_id) return;
    let active = true;
    setDocuments([]);
    setSourceError("");
    Promise.allSettled([api<DocumentRecord[]>("/api/documents"), api<DocumentRecord[]>(`/api/documents?case_id=${encodeURIComponent(run.case_id)}`)])
      .then((results) => {
        if (!active) return;
        setDocuments(results.flatMap((result) => result.status === "fulfilled" ? result.value : []));
        if (results.some((result) => result.status === "rejected")) setSourceError("Some source filenames could not be loaded. You can still open each citation.");
      })
      .catch(() => { if (active) setSourceError("Source filenames could not be loaded. You can still open each citation."); });
    return () => { active = false; };
  }, [run?.case_id]);
  useEffect(() => {
    if (!run || !(run.status === "queued" || run.status === "running")) return;
    const timer = setInterval(() => void load(), 1800);
    return () => clearInterval(timer);
  }, [load, run]);
  async function retry() {
    setRetrying(true);
    try { await api(`/api/runs/${id}/retry`, {method: "POST"}); await load(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setRetrying(false); }
  }
  const decision = run?.decision ?? null;
  if (!run && !error) return <Spinner label="Loading analysis…" />;
  if (!run) return <ErrorNotice message={error} retry={load} />;
  const processing = run.status === "queued" || run.status === "running";
  return (
    <>
      {sourceError && <ErrorNotice message={sourceError} />}
      <PageHeader
        eyebrow="Analysis"
        title="Assessment report"
        description={`Run ${run.id}`}
        actions={
          <>
            <DeleteButton endpoint={`/api/runs/${id}`} label="Delete report" redirect={`/cases/${run.case_id}`}
              confirmation="Permanently delete this report, its decision, saved analysis progress and local ticket records? Source documents remain. This cannot be undone." />
            <Link className="button button-quiet" href={`/cases/${run.case_id}`}>
              Back to case
            </Link>
          </>
        }
      />
      {error && <ErrorNotice message={error} />}
      <RunProgress run={run} />
      {processing && (
        <section className="card">
          <Spinner
            label={
              run.status === "queued"
                ? "The analysis is waiting for an available worker…"
                : "Retrieving evidence and evaluating requirements…"
            }
          />
        </section>
      )}
      {run.status === "failed" && (
        <div style={{marginBottom: 18}}>
          <ErrorNotice message={run.error || run.progress?.error || "The analysis failed."} />
          {user?.role !== "auditor" && <button className="button" disabled={retrying} onClick={retry}>{retrying ? "Resuming…" : "Resume unfinished requirements"}</button>}
          <p className="subtle">Completed requirement assessments are preserved.</p>
        </div>
      )}{" "}
      {run.report && !processing && run.status !== "failed" && (
        <>
          {run.report.workflow_error && (
            <div style={{ marginBottom: 18 }}>
              <ErrorNotice message={run.report.workflow_error} />
            </div>
          )}
          <div className="stat-grid">
            <article className="card stat">
              <span className="stat-label">Risk</span>
              <span className="stat-value">
                <StatusBadge value={run.report.risk}>
                  {run.report.risk}
                </StatusBadge>
              </span>
            </article>
            <article className="card stat">
              <span className="stat-label">Evidence completeness</span>
              <span className="stat-value">{run.report.completeness}%</span>
              <div className="progress-track">
                <div
                  className="progress-value"
                  style={{ width: `${run.report.completeness}%` }}
                />
              </div>
            </article>
            <article className="card stat">
              <span className="stat-label">Human decision</span>
              <span className="stat-value" style={{ fontSize: 18 }}>
                {decision ? (
                  <StatusBadge value={decision.decision}>
                    {statusLabels[decision.decision]}
                  </StatusBadge>
                ) : (
                  <StatusBadge value="awaiting_review">
                    Awaiting decision
                  </StatusBadge>
                )}
              </span>
            </article>
          </div>
          <section className="card report-summary">
            <h2>Summary</h2>
            <p>{run.report.summary}</p>
          </section>
          <div className="detail-grid" style={{ marginTop: 18 }}>
            <div className="stack">
              <section>
                <h2 style={{ font: "600 24px Georgia,serif" }}>
                  Findings ({run.report.findings.length})
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
                        {(finding.missing_information?.length ?? 0) > 0 && (
                          <div className="notice notice-info">
                            <p>
                              <strong>Missing information:</strong>{" "}
                              {finding.missing_information?.join(" ")}
                            </p>
                          </div>
                        )}
                        <div className="requirement-grid">
                          <div><h4>Policy requirement</h4>
                            <p>{finding.requirement_description ?? finding.requirement_source?.quote ?? "See the approved policy version for this requirement."}</p>
                            {finding.requirement_source && <button className="evidence-quote" onClick={() => setSource(finding.requirement_source!)}>
                              <span>{documents.find((document) => document.id === finding.requirement_source?.document_id)?.filename ?? "Policy source"} · View quoted passage</span>
                            </button>}
                          </div>
                          <div><h4>Counterparty evidence</h4>
                          {finding.evidence.length === 0 && <p className="subtle">No supporting evidence was found.</p>}
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
                                ? "independent evidence"
                                : "declaration"}{" "}
                              · {documents.find((document) => document.id === evidence.document_id)?.filename ?? "Source document"}
                              {" · "}View quoted passage
                            </span>
                          </button>
                        ))}
                          </div>
                        </div>
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
                  <h2>Execution trace</h2>
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
                      <dt>Assessment version</dt>
                      <dd className="mono">{run.report.rules_version}</dd>
                    </div>
                    <div>
                      <dt>Prompt</dt>
                      <dd className="mono">{run.report.prompt_version}</dd>
                    </div>
                    <div>
                      <dt>Duration</dt>
                      <dd>{run.report.metrics.duration_ms == null ? "Not recorded" : `${run.report.metrics.duration_ms} ms`}</dd>
                    </div>
                    <div>
                      <dt>Tokens</dt>
                      <dd>
                        {run.report.metrics.input_tokens} /{" "}
                        {run.report.metrics.output_tokens}
                      </dd>
                    </div>
                    <div>
                      <dt>Cost</dt>
                      <dd>
                        {run.report.metrics.cost_usd === null
                          ? "Cost unavailable"
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
    { key: "queued", label: "Created" },
    { key: "running", label: "Analysis" },
    { key: "awaiting_review", label: "Review" },
    { key: "completed", label: "Decision" },
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
        {run.progress && <div aria-live="polite" style={{marginTop: 18}}>
          <p>{run.progress.completed} of {run.progress.total} requirements assessed</p>
          <progress aria-label="Requirement assessment progress" value={run.progress.completed} max={Math.max(run.progress.total, 1)} style={{width: "100%"}} />
          {run.progress.current_requirement_id && <p className="subtle">Current requirement: {run.progress.current_requirement_id}</p>}
        </div>}
        {run.events && run.events.length > 0 && (
          <p
            className="subtle"
            style={{ textAlign: "center", margin: "14px 0 0" }}
          >
            {runEventLabel(run.events.at(-1)?.event ?? "")}
          </p>
        )}
      </div>
    </section>
  );
}

function runEventLabel(event: string): string {
  const labels: Record<string, string> = {
    "analysis.queued": "Analysis queued",
    "run.started": "Analysis started",
    "run.awaiting_review": "Report awaiting review",
    "analysis.decision": "Decision recorded",
    "run.completed": "Analysis completed",
    "run.retry_scheduled": "Analysis retry scheduled",
    "run.failed": "Analysis failed",
  };
  if (labels[event]) return labels[event];
  if (event.startsWith("run.") || event.startsWith("analysis.")) {
    return "Analysis status updated";
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
            <h2>Follow-up questions</h2>
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
            <h2>Discrepancies</h2>
          </div>
          <div className="card-body">
            <ul className="plain-list">
              {discrepancies.map((item, index) => (
                <li key={index}>{item.description}</li>
              ))}
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
        <h2>Decision</h2>
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
            A decision can be recorded after the report is ready.
          </p>
        ) : !canDecide ? (
          <p className="subtle">The report is awaiting a reviewer decision.</p>
        ) : (
          <form onSubmit={submit}>
            {error && <ErrorNotice message={error} />}
            <div className="decision-options">
              {(
                [
                  ["accepted", "Accept"],
                  ["rejected", "Reject"],
                  ["needs_information", "Request information"],
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
              <span>Decision rationale</span>
              <textarea
                className="textarea"
                required
                minLength={3}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Explain which findings informed the decision."
              />
            </label>
            <button
              className="button"
              style={{ width: "100%" }}
              disabled={pending || !rationale.trim()}
            >
              {pending ? "Saving…" : "Save decision"}
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
    `Information request — analysis ${run.id.slice(0, 8)}`,
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
        <h2>Follow-up ticket</h2>
      </div>
      <div className="card-body">
        {error && <ErrorNotice message={error} />}
        <p className="subtle">
          Proposal, approval, and submission to the service are three separate
          auditable steps.
        </p>
        {!canPropose ? (
          <p className="subtle">The auditor account has read-only access.</p>
        ) : (
          <>
            <label className="field">
              <span>Title</span>
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
              <span>Body</span>
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
                Return to editing
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
                  ? "Saving…"
                  : "Save exact proposal"}
              </button>
            </div>
          </div>
        ) : canPropose ? (
          <button
            className="button button-secondary button-small"
            disabled={!title.trim() || !body.trim()}
            onClick={() => setPreview(true)}
          >
            Preview proposal
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
                      "Ticket"}
                  </h4>
                  <StatusBadge value={approval.status}>
                    {statusLabels[approval.status] ?? approval.status}
                  </StatusBadge>
                </div>
                <p>{approval.arguments?.body ?? approval.ticket?.body}</p>
                <span className="subtle">
                  Expires: {formatDate(approval.expires_at)}
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
                  <DeleteButton endpoint={`/api/approvals/${approval.id}`} label="Delete local ticket record" onDeleted={saved}
                    confirmation="Permanently delete this local proposal and execution record? This does not cancel or delete a ticket already created in another service." />
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
                        Approve exact details
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
                        Execute write
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
                        Reconcile receipt
                      </button>
                    )}
                  {(approval.status === "executed" || approval.ticket) && (
                    <button
                      className="button button-quiet button-small"
                      disabled={!!pending}
                      onClick={() => refresh(approval.id)}
                    >
                      Refresh status
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
  return (
    <Modal title="Evidence source" close={close}>
      <div className="modal-content">
        {error && <ErrorNotice message={error} />}{" "}
        {!document && !error && <Spinner label="Loading document…" />}
        {document && (
          <>
            <p>
              <strong>{document.filename}</strong>
              <br />
              <span className="subtle">
                Quoted passage
              </span>
            </p>
            <blockquote className="source-document">
              <mark className="source-highlight">{citation.quote}</mark>
            </blockquote>
            <Link
              className="arrow-link"
              href={sourceHref(citation)}
            >
              Open full document <Icon name="arrow" />
            </Link>
          </>
        )}
      </div>
    </Modal>
  );
}
