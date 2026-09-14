"use client";

import Link from "next/link";
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
        eyebrow="Portfel ocen"
        title="Sprawy kontrahentów"
        description="Każda sprawa łączy kontekst relacji, dokumenty, analizy i decyzje w jednej historii."
        actions={
          <Link className="button" href="/cases/new">
            <Icon name="plus" />
            Nowa sprawa
          </Link>
        }
      />
      {error && <ErrorNotice message={error} retry={load} />}
      {loading ? (
        <Spinner label="Pobieranie spraw…" />
      ) : cases.length === 0 ? (
        <div className="card">
          <EmptyState
            title="Brak spraw"
            description="Utwórz pierwszą sprawę i opisz relację z kontrahentem."
            action={
              <Link className="button" href="/cases/new">
                Utwórz sprawę
              </Link>
            }
          />
        </div>
      ) : (
        <div className="card-grid">
          {cases.map((item) => (
            <Link
              className="card case-card"
              href={`/cases/${item.id}`}
              key={item.id}
            >
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
                    ? "Krytyczna relacja"
                    : item.relationship.business_criticality === "medium"
                      ? "Średnia krytyczność"
                      : "Niska krytyczność"}
                </StatusBadge>
                <span className="subtle">{formatDate(item.updated_at)}</span>
              </div>
              <h2>{item.name}</h2>
              <p className="counterparty">{item.counterparty_name}</p>
              <div className="case-card-footer">
                <span>
                  {item.relationship.personal_data
                    ? "Dane osobowe"
                    : "Bez danych osobowych"}
                </span>
                <span className="arrow-link">
                  Otwórz <Icon name="arrow" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
