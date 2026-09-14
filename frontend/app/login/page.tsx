"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { api, errorMessage } from "@/lib/api";
import { roleLabels } from "@/lib/format";
import type { DemoAccount } from "@/lib/types";
import { ErrorNotice, Spinner } from "@/components/ui";

export default function LoginPage() {
  const { user, meta, loading, login } = useAuth();
  const router = useRouter();
  const [nextPath, setNextPath] = useState("/cases");
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setNextPath(
      new URLSearchParams(globalThis.location.search).get("next") || "/cases",
    );
  }, []);

  useEffect(() => {
    if (!loading && user) router.replace(nextPath);
  }, [loading, nextPath, router, user]);

  useEffect(() => {
    if (meta?.demo_mode)
      api<DemoAccount[]>("/api/demo/accounts")
        .then(setAccounts)
        .catch((reason) => setError(errorMessage(reason)));
  }, [meta?.demo_mode]);

  function selectAccount(account: DemoAccount) {
    setEmail(account.email);
    setPassword(account.password);
    setError("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await login(email, password);
      router.replace(nextPath);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-brand">
        <div className="brand">
          <span className="brand-mark">A</span>
          <span>Aegis</span>
        </div>
        <div className="auth-brand-copy">
          <h1>Decyzje oparte na dowodach.</h1>
          <p>
            Porównuj dokumenty kontrahentów z zatwierdzonymi politykami, śledź
            źródła i zachowuj pełną historię decyzji.
          </p>
        </div>
        <span className="auth-footnote">
          Lokalne środowisko oceny ryzyka kontrahenta
        </span>
      </section>
      <section className="auth-panel">
        <form className="login-card" onSubmit={submit}>
          {meta?.demo_mode && (
            <div className="demo-callout">
              <strong>Tryb demonstracyjny</strong>
              <span>
                Dane są syntetyczne, a wyniki generuje jawnie oznaczony adapter
                demo.
              </span>
            </div>
          )}
          <p className="eyebrow">Bezpieczny dostęp</p>
          <h2>Zaloguj się</h2>
          <p>Wybierz konto demonstracyjne albo podaj dane sesji.</p>
          {loading && <Spinner label="Ładowanie konfiguracji…" />}
          {error && <ErrorNotice message={error} />}
          {accounts.length > 0 && (
            <>
              <span className="field-label">Konta demonstracyjne</span>
              <div className="demo-accounts">
                {accounts.map((account) => (
                  <button
                    type="button"
                    key={account.email}
                    className={`demo-account ${email === account.email ? "selected" : ""}`}
                    onClick={() => selectAccount(account)}
                  >
                    <div>
                      <strong>{account.name}</strong>
                      <span>{account.organization ?? account.email}</span>
                    </div>
                    <small>{roleLabels[account.role]}</small>
                  </button>
                ))}
              </div>
            </>
          )}
          <label className="field">
            <span>E-mail</span>
            <input
              className="input"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Hasło</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button
            className="button"
            style={{ width: "100%" }}
            disabled={pending || !email || !password}
          >
            {pending ? "Logowanie…" : "Zaloguj się"}
          </button>
        </form>
      </section>
    </main>
  );
}
