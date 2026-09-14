"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorNotice, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { AssessmentCase, Relationship } from "@/lib/types";

const emptyRelationship: Relationship = {
  purpose: "",
  data_shared: "",
  system_access: "",
  business_criticality: "medium",
  personal_data: false,
  privileged_access: false,
};

export default function NewCasePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [counterpartyName, setCounterpartyName] = useState("");
  const [relationship, setRelationship] = useState(emptyRelationship);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const set = <K extends keyof Relationship>(key: K, value: Relationship[K]) =>
    setRelationship((current) => ({ ...current, [key]: value }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const created = await api<AssessmentCase>("/api/cases", {
        method: "POST",
        body: JSON.stringify({
          name,
          counterparty_name: counterpartyName,
          relationship,
        }),
      });
      router.push(`/cases/${created.id}`);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Nowa ocena"
        title="Utwórz sprawę"
        description="Kontekst relacji decyduje, które wymagania będą miały zastosowanie. Opisz go konkretnie."
      />
      <form className="card" onSubmit={submit}>
        <div className="card-header">
          <h2>Dane sprawy i relacji</h2>
        </div>
        <div className="card-body">
          {error && <ErrorNotice message={error} />}
          <div className="form-grid">
            <label className="field">
              <span>Nazwa sprawy</span>
              <input
                className="input"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="np. Ocena dostawcy hostingu 2026"
              />
            </label>
            <label className="field">
              <span>Nazwa kontrahenta</span>
              <input
                className="input"
                required
                value={counterpartyName}
                onChange={(e) => setCounterpartyName(e.target.value)}
                placeholder="np. Northstar Labs"
              />
            </label>
          </div>
          <label className="field">
            <span>Cel współpracy</span>
            <textarea
              className="textarea"
              required
              value={relationship.purpose}
              onChange={(e) => set("purpose", e.target.value)}
              placeholder="Jaki proces biznesowy będzie obsługiwał kontrahent?"
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
                placeholder="Kategorie i zakres danych"
              />
            </label>
            <label className="field">
              <span>Dostęp do systemów</span>
              <textarea
                className="textarea"
                required
                value={relationship.system_access}
                onChange={(e) => set("system_access", e.target.value)}
                placeholder="Systemy, środowiska i poziom dostępu"
              />
            </label>
          </div>
          <label className="field">
            <span>Krytyczność biznesowa</span>
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
              <span>Relacja obejmuje przetwarzanie danych osobowych</span>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={relationship.privileged_access}
                onChange={(e) => set("privileged_access", e.target.checked)}
              />
              <span>Kontrahent otrzyma dostęp uprzywilejowany</span>
            </label>
          </div>
          <div className="form-actions">
            <Link href="/cases" className="button button-quiet">
              Anuluj
            </Link>
            <button className="button" disabled={pending}>
              {pending ? "Tworzenie…" : "Utwórz sprawę"}
            </button>
          </div>
        </div>
      </form>
    </>
  );
}
