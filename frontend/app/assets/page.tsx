"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell, PageHeading, ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api, type Asset, type Page, type Category, all } from "@/lib/api";
function Registry() {
  const { organization: o, siteId } = useWorkspace();
  const [data, setData] = useState<Page<Asset>>();
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    setPage(1);
    setCategory("");
    setData(undefined);
  }, [o, siteId]);
  useEffect(() => {
    if (!o) return;
    const c = new AbortController();
    setCategories([]);
    void all<Category>("categories/", o.id, c.signal)
      .then(setCategories)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [o]);
  const params = new URLSearchParams({
    page: String(page),
    include_archived: String(archived),
  });
  if (siteId) params.set("site", siteId);
  if (term) params.set("search", term);
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  const query = params.toString();
  useEffect(() => {
    if (!o) return;
    const c = new AbortController();
    setData(undefined);
    setError("");
    void api<Page<Asset>>(`assets/?${query}`, o.id, { signal: c.signal })
      .then(setData)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [o, query]);
  async function download() {
    if (!o) return;
    setExporting(true);
    try {
      const blob = await api<Blob>(`assets/export/?${query}`, o.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "maintainiq-assets.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="EQUIPMENT / ASSET REGISTRY"
        title="Your asset registry"
        description="Find equipment, understand its hierarchy, and retain every registry change."
        action={
          <div className="actions">
            {o &&
              ["admin", "manager", "engineer", "auditor"].includes(o.role) && (
                <button
                  className="button secondary"
                  onClick={() => void download()}
                  disabled={exporting}
                >
                  {exporting ? "Exporting…" : "Export CSV ↓"}
                </button>
              )}
            {o && ["admin", "manager"].includes(o.role) && (
              <Link className="button primary" href="/assets/new">
                + Register asset
              </Link>
            )}
          </div>
        }
      />
      <section className="panel registry-panel">
        <form
          className="filter-bar"
          onSubmit={(e) => {
            e.preventDefault();
            setTerm(search);
            setPage(1);
          }}
        >
          <label className="search-field">
            Search equipment
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tag, equipment, serial…"
              maxLength={100}
            />
          </label>
          <button className="button secondary" type="submit">
            Search
          </button>
          <label>
            Category
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="standby">Standby</option>
              <option value="out_of_service">Out of service</option>
            </select>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => {
                setArchived(e.target.checked);
                setPage(1);
              }}
            />
            Include archived
          </label>
        </form>
        <ErrorNotice error={error} />
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Authorized asset registry</caption>
            <thead>
              <tr>
                <th>Asset / tag</th>
                <th>Category</th>
                <th>Site</th>
                <th>Status</th>
                <th>Criticality</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data?.results.map((asset) => (
                <tr key={asset.id}>
                  <td>
                    <Link className="asset-title" href={`/assets/${asset.id}`}>
                      {asset.name}
                    </Link>
                    <small>
                      {asset.tag}
                      {asset.is_synthetic ? " · SYNTHETIC" : ""}
                    </small>
                  </td>
                  <td>{asset.category_name}</td>
                  <td>{asset.site_name}</td>
                  <td>
                    <span
                      className={`status ${asset.archived_at ? "archived" : asset.status}`}
                    >
                      {asset.archived_at
                        ? "Archived"
                        : asset.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td>
                    <span className={`criticality ${asset.criticality}`}>
                      {asset.criticality}
                    </span>
                  </td>
                  <td>
                    <Link
                      aria-label={`Open ${asset.tag}`}
                      href={`/assets/${asset.id}`}
                    >
                      ↗
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data && !error ? (
          <p className="empty-state" aria-live="polite">
            Loading authorized assets…
          </p>
        ) : data?.results.length === 0 ? (
          <p className="empty-state">
            No matching equipment. Try a different search or register an asset.
          </p>
        ) : null}
        <div className="pagination">
          <span>
            {data?.count ?? "—"} assets · Page {page}
          </span>
          <div className="actions">
            <button
              className="button secondary compact"
              disabled={!data?.previous}
              onClick={() => setPage((v) => v - 1)}
            >
              Previous
            </button>
            <button
              className="button secondary compact"
              disabled={!data?.next}
              onClick={() => setPage((v) => v + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
export default function PageComponent() {
  return (
    <Shell>
      <Registry />
    </Shell>
  );
}
