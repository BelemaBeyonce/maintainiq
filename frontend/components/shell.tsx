"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useWorkspace } from "./workspace";
export function Shell({ children }: { children: ReactNode }) {
  const w = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!w.loading && !w.context) router.replace("/login");
  }, [w.loading, w.context, router]);
  if (w.loading || !w.context)
    return (
      <main className="loading" aria-live="polite">
        Opening your workspace…
      </main>
    );
  const o = w.organization;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-symbol">M</span>
          <span>
            Maintain<span className="brand-gold">IQ</span>
            <small>MAINTENANCE FOUNDATION</small>
          </span>
        </Link>
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <Link
            className={pathname === "/dashboard" ? "active" : ""}
            href="/dashboard"
          >
            <span aria-hidden>▦</span> Overview
          </Link>
          <Link
            className={pathname.startsWith("/assets") ? "active" : ""}
            href="/assets"
          >
            <span aria-hidden>◈</span> Asset registry
          </Link>
          {o && ["admin", "manager"].includes(o.role) && (
            <Link
              className={pathname === "/organization" ? "active" : ""}
              href="/organization"
            >
              <span aria-hidden>⚙</span> Organization & access
            </Link>
          )}
        </nav>
        <div className="sidebar-note">
          <span className="small-kicker">MILESTONE 01</span>
          <p>
            A reliable foundation.
            <br />
            One asset at a time.
          </p>
          <small>
            Work orders and reliability insights arrive in later milestones.
          </small>
        </div>
        <div className="profile">
          <span className="avatar">{w.context.user.name.charAt(0) || "U"}</span>
          <div>
            <strong>{w.context.user.name || w.context.user.email}</strong>
            <small>{o?.role || "No organization"}</small>
          </div>
        </div>
        <button
          className="signout"
          onClick={() => {
            void w.signOut().catch((e) => setError(e.message));
          }}
        >
          Sign out
        </button>
        {error && <p role="alert">{error}</p>}
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="switchers">
            <label>
              Organization
              <select
                aria-label="Organization"
                value={o?.id || ""}
                onChange={(e) => w.selectOrganization(e.target.value)}
              >
                {w.context.organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Site
              <select
                aria-label="Site"
                value={w.siteId}
                onChange={(e) => w.selectSite(e.target.value)}
              >
                <option value="">All permitted sites</option>
                {o?.sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <span className="environment-badge">
            {o?.is_synthetic ? "SYNTHETIC DEMO" : "AUTHORIZED WORKSPACE"}
          </span>
        </header>
        <main id="main" className="page-content">
          {o ? (
            children
          ) : (
            <section className="panel">
              <h1>No organization access</h1>
              <p>
                Ask an organization administrator for an invitation. Access is
                never self-assigned.
              </p>
            </section>
          )}
        </main>
        <footer className="footer">
          MaintainIQ · Smart maintenance. Institutional memory. Better
          decisions.<span>Foundation / M1</span>
        </footer>
      </div>
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <div role="alert" className="error-notice">
      {error}
    </div>
  ) : null;
}
