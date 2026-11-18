"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell, PageHeading, ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api, type Asset, type Page } from "@/lib/api";
type Counts = {
  total_assets: number;
  archived_assets: number;
  critical_assets: number;
  status_counts: { status: string; count: number }[];
  synthetic: boolean;
};
function Dashboard() {
  const { organization: o, siteId } = useWorkspace();
  const [data, setData] = useState<Counts>();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!o) return;
    const c = new AbortController();
    setData(undefined);
    setAssets([]);
    setError("");
    const query = siteId ? `?site=${siteId}` : "";
    void Promise.all([
      api<Counts>(`dashboard/${query}`, o.id, { signal: c.signal }),
      api<Page<Asset>>(`assets/${query}`, o.id, { signal: c.signal }),
    ])
      .then(([counts, page]) => {
        setData(counts);
        setAssets(page.results.slice(0, 5));
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [o, siteId]);
  const canWrite = o && ["admin", "manager"].includes(o.role);
  return (
    <>
      <PageHeading
        eyebrow="YOUR MAINTENANCE WORKSPACE"
        title="A clearer view of your assets."
        description="Equipment visibility across your authorized organization and sites."
        action={
          canWrite && (
            <Link className="button primary" href="/assets/new">
              + Register asset
            </Link>
          )
        }
      />
      <ErrorNotice error={error} />
      {o?.is_synthetic && (
        <div className="demo-banner">
          <span className="gold-dot" />
          <strong>Synthetic demonstration</strong>
          <span>
            All equipment records in this organization are examples, not
            operating results.
          </span>
        </div>
      )}
      <div className="metric-grid">
        {[
          {
            label: "Registered assets",
            value: data?.total_assets,
            detail: "Active registry records",
            symbol: "◈",
          },
          {
            label: "Critical equipment",
            value: data?.critical_assets,
            detail: "User-assigned criticality",
            symbol: "◇",
          },
          {
            label: "Sites in your scope",
            value: siteId ? 1 : o?.sites.length,
            detail: "Permission-aware visibility",
            symbol: "⌖",
          },
          {
            label: "Archived assets",
            value: data?.archived_assets,
            detail: "History retained",
            symbol: "↗",
          },
        ].map((item) => (
          <section className="metric" key={item.label}>
            <span className="metric-symbol" aria-hidden>
              {item.symbol}
            </span>
            <p>{item.label}</p>
            <strong>{item.value === undefined ? "—" : item.value}</strong>
            <small>{item.detail}</small>
          </section>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">ASSET REGISTER</span>
              <h2>Equipment in view</h2>
            </div>
            <Link className="text-link" href="/assets">
              View registry →
            </Link>
          </div>
          {!data && !error ? (
            <p aria-live="polite">Loading authorized records…</p>
          ) : assets.length ? (
            <div className="equipment-list">
              {assets.map((asset) => (
                <Link
                  className="equipment-row"
                  key={asset.id}
                  href={`/assets/${asset.id}`}
                >
                  <span className="equipment-icon" aria-hidden>
                    ◈
                  </span>
                  <div>
                    <strong>{asset.name}</strong>
                    <small>
                      {asset.tag} · {asset.category_name}
                    </small>
                  </div>
                  <span className={`status ${asset.status}`}>
                    {asset.status.replaceAll("_", " ")}
                  </span>
                  <span aria-hidden>↗</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="empty-state">
              No assets registered in this scope yet.
            </p>
          )}
        </section>
        <section className="panel status-panel">
          <span className="eyebrow">REGISTRY STATUS</span>
          <h2>Equipment status</h2>
          <p className="muted">
            Recorded by your team. Not live sensor readings.
          </p>
          {["active", "standby", "out_of_service"].map((status) => {
            const count =
              data?.status_counts.find((row) => row.status === status)?.count ||
              0;
            return (
              <div className="status-breakdown" key={status}>
                <div>
                  <span>{status.replaceAll("_", " ")}</span>
                  <strong>{data ? count : "—"}</strong>
                </div>
                <div className="bar-track">
                  <span
                    style={{
                      width: data?.total_assets
                        ? `${(count / data.total_assets) * 100}%`
                        : "0%",
                    }}
                  />
                </div>
              </div>
            );
          })}
          <div className="foundation-note">
            A foundation for better decisions.
            <br />
            <small>
              Maintenance workflows and reliability learning are not part of
              this milestone.
            </small>
          </div>
        </section>
      </div>
    </>
  );
}
export default function PageComponent() {
  return (
    <Shell>
      <Dashboard />
    </Shell>
  );
}
