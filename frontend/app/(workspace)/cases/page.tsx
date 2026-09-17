"use client";

import Link from "next/link";
import { DeleteButton } from "@/components/delete-button";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import {
  EmptyState,
  ErrorNotice,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AssessmentCase } from "@/lib/types";

export default function CasesPage() {
  const [cases, setCases] = useState<AssessmentCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setCases(await api<AssessmentCase[]>("/api/cases"));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Assessment portfolio"
        title="Counterparty cases"
        description="Each case keeps the relationship context, documents, analyses, and decisions in one history."
        actions={
          <Link className="button" href="/cases/new">
            <Icon name="plus" />
            New case
          </Link>
        }
      />
      {error && <ErrorNotice message={error} retry={load} />}
      {loading ? (
        <Spinner label="Loading cases…" />
      ) : cases.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No cases"
            description="Create your first case and describe the counterparty relationship."
            action={
              <Link className="button" href="/cases/new">
                Create case
              </Link>
            }
          />
        </div>
      ) : (
        <div className="card-grid">
          {cases.map((item) => (
            <article className="card case-card" key={item.id}>
              <Link className="case-card-content" href={`/cases/${item.id}`}>
              <div className="case-card-top">
                <StatusBadge
                  value={
                    item.relationship.business_criticality === "high"
                      ? "High"
                      : item.relationship.business_criticality === "medium"
                        ? "Medium"
                        : "Low"
                  }
                >
                  {item.relationship.business_criticality === "high"
                    ? "Critical relationship"
                    : item.relationship.business_criticality === "medium"
                      ? "Medium criticality"
                      : "Low criticality"}
                </StatusBadge>
                <span className="subtle">{formatDate(item.updated_at)}</span>
              </div>
              <h2>{item.name}</h2>
              <p className="counterparty">{item.counterparty_name}</p>
              </Link>
              <div className="case-card-footer">
                <span>
                  {item.relationship.personal_data
                    ? "Personal data"
                    : "No personal data"}
                </span>
                <div className="row-actions">
                  <Link className="arrow-link" href={`/cases/${item.id}`}>Open <Icon name="arrow" /></Link>
                  <DeleteButton reviewerOnly endpoint={`/api/cases/${item.id}`} label="Delete" ariaLabel={`Delete ${item.name}`} onDeleted={load}
                    confirmation={`Permanently delete “${item.name}”, its documents, reports and decisions? Shared policies remain. This cannot be undone.`} />
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
