"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Shell, PageHeading, ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api, type Asset, type Page } from "@/lib/api";
type Event = {
  id: string;
  action: string;
  actor_name: string;
  timestamp: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};
function Detail() {
  const { id } = useParams<{ id: string }>();
  const { organization: o } = useWorkspace();
  const [asset, setAsset] = useState<Asset>();
  const [events, setEvents] = useState<Page<Event>>();
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!o) return;
      setError("");
      const record = await api<Asset>(
        `assets/${id}/?include_archived=true`,
        o.id,
        { signal },
      );
      setAsset(record);
      if (o.role !== "requester")
        setEvents(
          await api<Page<Event>>(
            `assets/${id}/history/?include_archived=true&page=${page}`,
            o.id,
            { signal },
          ),
        );
    },
    [id, o, page],
  );
  useEffect(() => {
    const c = new AbortController();
    setAsset(undefined);
    setEvents(undefined);
    void load(c.signal).catch((e) => {
      if (!c.signal.aborted) setError(e.message);
    });
    return () => c.abort();
  }, [load]);
  async function archive() {
    if (
      !o ||
      !asset ||
      !confirm(
        "Archive this asset? Its registry history will be retained. Active children must be archived or reparented first.",
      )
    )
      return;
    setBusy(true);
    try {
      await api(`assets/${id}/`, o.id, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Archive failed");
    } finally {
      setBusy(false);
    }
  }
  if (!asset)
    return (
      <>
        <Link className="text-link" href="/assets">
          ← Asset registry
        </Link>
        <ErrorNotice error={error} />
        {!error && <p aria-live="polite">Loading equipment record…</p>}
      </>
    );
  const canWrite =
    o && ["admin", "manager"].includes(o.role) && !asset.archived_at;
  return (
    <>
      <Link className="breadcrumb" href="/assets">
        ← Asset registry
      </Link>
      <PageHeading
        eyebrow={`${asset.tag} / EQUIPMENT RECORD`}
        title={asset.name}
        description={`${asset.site_name} · ${asset.category_name}`}
        action={
          canWrite && (
            <div className="actions">
              <Link className="button secondary" href={`/assets/${id}/edit`}>
                Edit record
              </Link>
              <button
                className="button danger"
                disabled={busy}
                onClick={() => void archive()}
              >
                {busy ? "Archiving…" : "Archive asset"}
              </button>
            </div>
          )
        }
      />
      <ErrorNotice error={error} />
      {asset.archived_at && (
        <div className="archive-banner" role="status">
          Archived · This record is retained for historical evidence and cannot
          be edited.
        </div>
      )}
      <div className="detail-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>Equipment profile</h2>
            <span className={`status ${asset.status}`}>
              {asset.status.replaceAll("_", " ")}
            </span>
          </div>
          <dl className="detail-list">
            {[
              ["Asset tag", asset.tag],
              ["Category", asset.category_name],
              ["Manufacturer", asset.manufacturer],
              ["Model", asset.model],
              ["Serial number", asset.serial_number],
              ["Criticality", asset.criticality],
              ["Site", asset.site_name],
              ["Functional location", asset.location_code],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || "Not recorded"}</dd>
              </div>
            ))}
            <div>
              <dt>Parent asset</dt>
              <dd>
                {asset.parent_id ? (
                  <Link
                    className="text-link"
                    href={`/assets/${asset.parent_id}`}
                  >
                    Open parent equipment →
                  </Link>
                ) : (
                  "Top-level equipment"
                )}
              </dd>
            </div>
          </dl>
          <h3>Description</h3>
          <p className="preserve-space">
            {asset.description || "No description recorded."}
          </p>
          {asset.is_synthetic && (
            <p className="synthetic-note">
              Synthetic equipment. Not an actual field operating record.
            </p>
          )}
        </section>
        <section className="panel">
          <span className="eyebrow">TRACEABLE REGISTRY CHANGES</span>
          <h2>Asset history</h2>
          <p className="muted">
            An append-only timeline of authorized registry actions.
          </p>
          {o?.role === "requester" ? (
            <p>Your requester role does not include history access.</p>
          ) : (
            <>
              <ol className="timeline">
                {events?.results.map((event) => (
                  <li key={event.id}>
                    <span className="timeline-dot" />
                    <strong>{event.action.replace("asset.", "Asset ")}</strong>
                    <p>{event.actor_name || "System"}</p>
                    <time dateTime={event.timestamp}>
                      {new Date(event.timestamp).toLocaleString()}
                    </time>
                    <details>
                      <summary>View recorded changes</summary>
                      <pre>
                        {JSON.stringify(
                          { before: event.before, after: event.after },
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                  </li>
                ))}
              </ol>
              {events?.results.length === 0 && (
                <p>No registry changes are recorded for this asset.</p>
              )}
              <div className="pagination">
                <span>{events?.count || 0} events</span>
                <div className="actions">
                  <button
                    className="button secondary compact"
                    disabled={!events?.previous}
                    onClick={() => setPage((v) => v - 1)}
                  >
                    Previous
                  </button>
                  <button
                    className="button secondary compact"
                    disabled={!events?.next}
                    onClick={() => setPage((v) => v + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
export default function PageComponent() {
  return (
    <Shell>
      <Detail />
    </Shell>
  );
}
