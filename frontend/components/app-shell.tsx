"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/context/auth-context";
import { roleLabels } from "@/lib/format";
import { Icon } from "./icons";
import { Spinner } from "./ui";

const links = [
  { href: "/cases", label: "Sprawy", icon: "cases" as const },
  { href: "/policies", label: "Polityki", icon: "policy" as const },
  { href: "/audit", label: "Historia", icon: "audit" as const },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, meta, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, pathname, router, user]);

  if (loading || !user)
    return (
      <main className="main">
        <Spinner label="Sprawdzanie sesji…" />
      </main>
    );

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" href="/cases">
          <span className="brand-mark">A</span>
          <span>Aegis</span>
        </Link>
        {meta?.demo_mode && (
          <div className="demo-pill">
            <span className="demo-dot" />
            <span>Tryb demo</span>
          </div>
        )}
        <nav className="nav" aria-label="Główna nawigacja">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={pathname.startsWith(link.href) ? "active" : ""}
            >
              <Icon name={link.icon} />
              <span>{link.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-user">
          <strong>{user.name}</strong>
          <span>{roleLabels[user.role]}</span>
          <button className="logout-button" onClick={handleLogout}>
            <Icon name="logout" />
            <span>Wyloguj</span>
          </button>
        </div>
      </aside>
      <section className="workspace">
        <div className="topbar">
          <div className="model-indicator">
            <span className="demo-dot" />
            <span>
              Model: <b>{meta?.model_name ?? meta?.model_mode ?? "—"}</b>
            </span>
          </div>
        </div>
        <main className="main">{children}</main>
      </section>
    </div>
  );
}
