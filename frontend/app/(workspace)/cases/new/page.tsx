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
        eyebrow="New assessment"
        title="Create case"
        description="The relationship context determines which requirements apply. Describe it precisely."
      />
      <form className="card" onSubmit={submit}>
        <div className="card-header">
          <h2>Case and relationship details</h2>
        </div>
        <div className="card-body">
          {error && <ErrorNotice message={error} />}
          <div className="form-grid">
            <label className="field">
              <span>Case name</span>
              <input
                className="input"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Hosting provider assessment 2026"
              />
            </label>
            <label className="field">
              <span>Counterparty name</span>
              <input
                className="input"
                required
                value={counterpartyName}
                onChange={(e) => setCounterpartyName(e.target.value)}
                placeholder="e.g. Northstar Labs"
              />
            </label>
          </div>
          <label className="field">
            <span>Relationship purpose</span>
            <textarea
              className="textarea"
              required
              value={relationship.purpose}
              onChange={(e) => set("purpose", e.target.value)}
              placeholder="Which business process will the counterparty support?"
            />
          </label>
          <div className="form-grid">
            <label className="field">
              <span>Data shared</span>
              <textarea
                className="textarea"
                required
                value={relationship.data_shared}
                onChange={(e) => set("data_shared", e.target.value)}
                placeholder="Data categories and scope"
              />
            </label>
            <label className="field">
              <span>System access</span>
              <textarea
                className="textarea"
                required
                value={relationship.system_access}
                onChange={(e) => set("system_access", e.target.value)}
                placeholder="Systems, environments, and access level"
              />
            </label>
          </div>
          <label className="field">
            <span>Business criticality</span>
            <select
              className="select"
              value={relationship.business_criticality}
              onChange={(e) => set("business_criticality", e.target.value)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <div className="form-grid">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={relationship.personal_data}
                onChange={(e) => set("personal_data", e.target.checked)}
              />
              <span>The relationship involves personal data processing</span>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={relationship.privileged_access}
                onChange={(e) => set("privileged_access", e.target.checked)}
              />
              <span>The counterparty will receive privileged access</span>
            </label>
          </div>
          <div className="form-actions">
            <Link href="/cases" className="button button-quiet">
              Cancel
            </Link>
            <button className="button" disabled={pending}>
              {pending ? "Creating…" : "Create case"}
            </button>
          </div>
        </div>
      </form>
    </>
  );
}
