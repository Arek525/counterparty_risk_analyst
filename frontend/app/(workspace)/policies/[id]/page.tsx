"use client";

import Link from "next/link";
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
import { formatDate, formatLocation, statusLabels } from "@/lib/format";
import type { PolicyVersion, Requirement } from "@/lib/types";

export default function PolicyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [policy, setPolicy] = useState<PolicyVersion | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try {
      const value = await api<PolicyVersion>(`/api/policies/${id}`);
      setPolicy(value);
      setRequirements(value.requirements ?? []);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }
  useEffect(() => {
    void load();
  }, [id]);
  async function save() {
    setPending(true);
    setError("");
    try {
      const value = await api<PolicyVersion>(
        `/api/policies/${id}/requirements`,
        { method: "PUT", body: JSON.stringify({ requirements }) },
      );
      setPolicy(value);
      setRequirements(value.requirements ?? requirements);
      setEditing(false);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
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
  async function clone() {
    setPending(true);
    setError("");
    try {
      const value = await api<PolicyVersion>(`/api/policies/${id}/clone`, {
        method: "POST",
      });
      router.push(`/policies/${value.id}`);
    } catch (reason) {
      setError(errorMessage(reason));
      setPending(false);
    }
  }
  if (!policy && !error) return <Spinner label="Loading policy…" />;
  if (!policy) return <ErrorNotice message={error} retry={load} />;
  const canEdit = policy.status === "draft" && user?.role !== "auditor";
  const canApprove =
    policy.status === "draft" &&
    (user?.role === "reviewer" || user?.role === "administrator");
  return (
    <>
      <PageHeader
        eyebrow={`Version ${policy.version}`}
        title={policy.name}
        description={`Created ${formatDate(policy.created_at)}`}
        actions={
          <>
            <StatusBadge value={policy.status}>
              {statusLabels[policy.status]}
            </StatusBadge>
            {policy.status === "approved" && user?.role !== "auditor" && (
              <button
                className="button button-secondary"
                onClick={clone}
                disabled={pending}
              >
                Clone for editing
              </button>
            )}
            {canEdit && !editing && (
              <button
                className="button button-secondary"
                onClick={() => setEditing(true)}
              >
                Edit requirements
              </button>
            )}
            {editing && (
              <button
                className="button button-quiet"
                onClick={() => {
                  setRequirements(policy.requirements);
                  setEditing(false);
                }}
              >
                Cancel editing
              </button>
            )}
            {editing && (
              <button className="button" onClick={save} disabled={pending}>
                {pending ? "Saving…" : "Save requirements"}
              </button>
            )}
            {canApprove && !editing && (
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
              ? "Analyses reference this exact version. Changes require a new draft version."
              : "Review the meaning and source quote of every requirement before approval."}
          </p>
        </div>
      </div>
      {requirements.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No requirements"
            description="The adapter proposed no requirements for the selected sources."
          />
        </div>
      ) : (
        <div className="requirements">
          {requirements.map((requirement, index) =>
            editing ? (
              <RequirementEditor
                key={requirement.id}
                value={requirement}
                change={(value) =>
                  setRequirements((current) =>
                    current.map((entry, i) => (i === index ? value : entry)),
                  )
                }
                remove={() =>
                  setRequirements((current) =>
                    current.filter((_, i) => i !== index),
                  )
                }
              />
            ) : (
              <RequirementCard key={requirement.id} requirement={requirement} />
            ),
          )}
        </div>
      )}
    </>
  );
}

function RequirementCard({ requirement }: { requirement: Requirement }) {
  return (
    <article className="card requirement">
      <div className="requirement-head">
        <div>
          <h3>{requirement.title}</h3>
          <span className="mono">{requirement.id}</span>
        </div>
        <StatusBadge value={requirement.severity}>
          {requirement.severity}
        </StatusBadge>
      </div>
      <div className="requirement-grid">
        <div>
          <label>Condition</label>
          <strong>
            {requirement.field} {requirement.operator}{" "}
            {String(requirement.expected)}
          </strong>
        </div>
        <div>
          <label>Evaluation</label>
          <strong>{requirement.evaluation_method}</strong>
        </div>
        <div>
          <label>Applicability</label>
          <strong>
            {Object.keys(requirement.applicability).length
              ? JSON.stringify(requirement.applicability)
              : "Always"}
          </strong>
        </div>
      </div>
      <div className="source-box">
        <q>{requirement.source.quote}</q>
        <small>
          <Link
            className="arrow-link"
            href={`/documents/${requirement.source.document_id}?chunk=${requirement.source.chunk_id}`}
          >
            Open source · {formatLocation(requirement.source.location)}{" "}
            <Icon name="arrow" />
          </Link>
        </small>
      </div>
    </article>
  );
}

function RequirementEditor({
  value,
  change,
  remove,
}: {
  value: Requirement;
  change: (value: Requirement) => void;
  remove: () => void;
}) {
  const update = <K extends keyof Requirement>(key: K, next: Requirement[K]) =>
    change({ ...value, [key]: next });
  const [expectedText, setExpectedText] = useState(
    typeof value.expected === "string"
      ? value.expected
      : JSON.stringify(value.expected),
  );
  const [applicabilityText, setApplicabilityText] = useState(
    JSON.stringify(value.applicability),
  );
  const [applicabilityError, setApplicabilityError] = useState("");

  function changeExpected(raw: string) {
    setExpectedText(raw);
    if (value.operator === "lte" || value.operator === "gte") {
      const parsed = Number(raw);
      if (Number.isFinite(parsed)) update("expected", parsed);
      return;
    }
    if (
      raw === "true" ||
      raw === "false" ||
      raw === "null" ||
      raw.startsWith("[")
    ) {
      try {
        update("expected", JSON.parse(raw));
        return;
      } catch {}
    }
    update("expected", raw);
  }

  function changeApplicability(raw: string) {
    setApplicabilityText(raw);
    try {
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("not an object");
      }
      update("applicability", parsed as Record<string, unknown>);
      setApplicabilityError("");
    } catch {
      setApplicabilityError(
        'Enter a valid JSON object, for example {"personal_data":true}.',
      );
    }
  }
  return (
    <article className="card requirement">
      <div className="requirement-edit-grid">
        <label className="field">
          <span>Title</span>
          <input
            className="input"
            value={value.title}
            onChange={(e) => update("title", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Severity</span>
          <select
            className="select"
            value={value.severity}
            onChange={(e) =>
              update("severity", e.target.value as Requirement["severity"])
            }
          >
            <option>Low</option>
            <option>Medium</option>
            <option>High</option>
          </select>
        </label>
        <label className="field">
          <span>Method</span>
          <select
            className="select"
            value={value.evaluation_method}
            onChange={(e) =>
              update(
                "evaluation_method",
                e.target.value as Requirement["evaluation_method"],
              )
            }
          >
            <option value="deterministic">deterministic</option>
            <option value="llm">llm</option>
            <option value="manual">manual</option>
          </select>
        </label>
      </div>
      <div className="requirement-edit-grid">
        <label className="field">
          <span>Field</span>
          <input
            className="input"
            value={value.field}
            onChange={(e) => update("field", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Operator</span>
          <select
            className="select"
            value={value.operator}
            onChange={(e) =>
              update("operator", e.target.value as Requirement["operator"])
            }
          >
            {["eq", "lte", "gte", "contains", "present", "manual"].map(
              (entry) => (
                <option key={entry}>{entry}</option>
              ),
            )}
          </select>
        </label>
        <label className="field">
          <span>Expected value</span>
          <input
            className="input"
            inputMode={
              value.operator === "lte" || value.operator === "gte"
                ? "decimal"
                : "text"
            }
            value={expectedText}
            onChange={(e) => changeExpected(e.target.value)}
          />
        </label>
      </div>
      <label className="field">
        <span>Applicability conditions (JSON)</span>
        <input
          className="input mono"
          value={applicabilityText}
          onChange={(e) => changeApplicability(e.target.value)}
          aria-invalid={Boolean(applicabilityError)}
        />
        {applicabilityError && (
          <small className="field-help" style={{ color: "var(--red)" }}>
            {applicabilityError}
          </small>
        )}
      </label>
      <div className="source-box">
        <q>{value.source.quote}</q>
        <small>
          The quote remains linked to {formatLocation(value.source.location)}.
        </small>
      </div>
      <div className="form-actions">
        <button
          className="button button-small button-danger"
          type="button"
          onClick={remove}
        >
          Remove requirement
        </button>
      </div>
    </article>
  );
}
