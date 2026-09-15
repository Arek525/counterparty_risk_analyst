"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { ErrorNotice } from "./ui";

export function DeleteButton({ endpoint, label, ariaLabel, confirmation, redirect, onDeleted }: {
  endpoint: string;
  label: string;
  ariaLabel?: string;
  confirmation: string;
  redirect?: string;
  onDeleted?: () => void | Promise<void>;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  if (!user || user.role === "auditor") return null;

  async function remove() {
    if (!confirm(confirmation)) return;
    setPending(true);
    setError("");
    try {
      const result = await api<{cleanup_pending?: boolean}>(endpoint, { method: "DELETE" });
      if (result.cleanup_pending) alert("The record was deleted. Original file cleanup is pending and will retry automatically.");
      if (redirect) router.push(redirect);
      else await onDeleted?.();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  return <div className="delete-control">
    <button type="button" className="button button-small button-danger delete-button" aria-label={ariaLabel} disabled={pending} onClick={remove}>
      {pending ? "Deleting…" : label}
    </button>
    {error && <ErrorNotice message={error} />}
  </div>;
}
