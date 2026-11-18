"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  all,
  type Asset,
  type AssetInput,
  type Category,
  type Location,
} from "@/lib/api";
import { useWorkspace } from "./workspace";
import { ErrorNotice, PageHeading } from "./shell";
export function AssetForm({ initial }: { initial?: Asset }) {
  const { organization: o, siteId } = useWorkspace();
  const router = useRouter();
  const [form, setForm] = useState<AssetInput>({
    tag: initial?.tag || "",
    name: initial?.name || "",
    site_id: initial?.site_id || siteId || o?.sites[0]?.id || "",
    category_id: initial?.category_id || "",
    functional_location_id: initial?.functional_location_id || null,
    parent_id: initial?.parent_id || null,
    manufacturer: initial?.manufacturer || "",
    model: initial?.model || "",
    serial_number: initial?.serial_number || "",
    status: initial?.status || "active",
    criticality: initial?.criticality || "medium",
    description: initial?.description || "",
  });
  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [parents, setParents] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!o) return;
    const c = new AbortController();
    setLoading(true);
    setError("");
    const site = form.site_id;
    void Promise.all([
      all<Category>("categories/", o.id, c.signal),
      site
        ? all<Location>(`locations/?site=${site}`, o.id, c.signal)
        : Promise.resolve([]),
      site
        ? all<Asset>(`assets/?site=${site}`, o.id, c.signal)
        : Promise.resolve([]),
    ])
      .then(([cats, locs, assets]) => {
        setCategories(cats);
        setLocations(locs);
        setParents(assets.filter((a) => a.id !== initial?.id));
        setForm((current) => ({
          ...current,
          category_id: current.category_id || cats[0]?.id || "",
        }));
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [o, form.site_id, initial?.id]);
  function field<K extends keyof AssetInput>(name: K, value: AssetInput[K]) {
    setForm((current) => ({ ...current, [name]: value }));
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!o || busy) return;
    setBusy(true);
    setError("");
    try {
      const saved = await api<Asset>(
        initial ? `assets/${initial.id}/` : "assets/",
        o.id,
        { method: initial ? "PATCH" : "POST", body: JSON.stringify(form) },
      );
      router.push(`/assets/${saved.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save asset");
    } finally {
      setBusy(false);
    }
  }
  if (o && !["admin", "manager"].includes(o.role))
    return (
      <section className="panel">
        <h1>Registry changes require a manager</h1>
        <p>Your current role has read-only asset access.</p>
        <Link href="/assets" className="text-link">
          Return to the registry
        </Link>
      </section>
    );
  return (
    <>
      <PageHeading
        eyebrow="ASSET REGISTRY / EQUIPMENT RECORD"
        title={initial ? "Edit equipment record" : "Register an asset"}
        description="Build a clear, traceable equipment record. Required fields are marked *."
      />
      <form className="panel asset-form" onSubmit={submit}>
        <ErrorNotice error={error} />
        <div className="form-section-heading">
          <span className="section-number">01</span>
          <div>
            <h2>Equipment identity</h2>
            <p>Use a unique tag within your organization.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Asset tag *
            <input
              required
              maxLength={60}
              value={form.tag}
              onChange={(e) => field("tag", e.target.value)}
              placeholder="e.g. P-102"
            />
          </label>
          <label>
            Asset name *
            <input
              required
              maxLength={160}
              value={form.name}
              onChange={(e) => field("name", e.target.value)}
              placeholder="e.g. Process water pump"
            />
          </label>
          <label>
            Category *
            <select
              required
              value={form.category_id}
              onChange={(e) => field("category_id", e.target.value)}
            >
              <option value="">Select a category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Serial number
            <input
              maxLength={120}
              value={form.serial_number}
              onChange={(e) => field("serial_number", e.target.value)}
            />
          </label>
          <label>
            Manufacturer
            <input
              maxLength={100}
              value={form.manufacturer}
              onChange={(e) => field("manufacturer", e.target.value)}
            />
          </label>
          <label>
            Model
            <input
              maxLength={100}
              value={form.model}
              onChange={(e) => field("model", e.target.value)}
            />
          </label>
        </div>
        <div className="form-section-heading">
          <span className="section-number">02</span>
          <div>
            <h2>Location & hierarchy</h2>
            <p>
              Only sites and related equipment within your authorized scope are
              available.
            </p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Site *
            <select
              required
              disabled={!!initial}
              value={form.site_id}
              onChange={(e) => {
                setForm((current) => ({
                  ...current,
                  site_id: e.target.value,
                  functional_location_id: null,
                  parent_id: null,
                }));
              }}
            >
              <option value="">Select a site</option>
              {o?.sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Functional location
            <select
              value={form.functional_location_id || ""}
              onChange={(e) =>
                field("functional_location_id", e.target.value || null)
              }
            >
              <option value="">No functional location</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.code} · {l.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Parent asset
            <select
              value={form.parent_id || ""}
              onChange={(e) => field("parent_id", e.target.value || null)}
            >
              <option value="">No parent / top-level equipment</option>
              {parents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.tag} · {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-section-heading">
          <span className="section-number">03</span>
          <div>
            <h2>Registry classification</h2>
            <p>
              These are recorded classifications, not live condition
              measurements.
            </p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Status
            <select
              value={form.status}
              onChange={(e) => field("status", e.target.value)}
            >
              <option value="active">Active</option>
              <option value="standby">Standby</option>
              <option value="out_of_service">Out of service</option>
            </select>
          </label>
          <label>
            Criticality
            <select
              value={form.criticality}
              onChange={(e) => field("criticality", e.target.value)}
            >
              {["low", "medium", "high", "critical"].map((c) => (
                <option key={c} value={c}>
                  {c[0].toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <label className="span-two">
            Description
            <textarea
              maxLength={5000}
              rows={4}
              value={form.description}
              onChange={(e) => field("description", e.target.value)}
              placeholder="Equipment purpose and registry notes. Do not enter credentials or sensitive operating instructions."
            />
          </label>
        </div>
        {!loading && categories.length === 0 && (
          <p className="error-notice">
            An administrator must create a category in Organization & access
            before you can register equipment.
          </p>
        )}
        <div className="form-actions">
          <Link
            className="button secondary"
            href={initial ? `/assets/${initial.id}` : "/assets"}
          >
            Cancel
          </Link>
          <button
            className="button primary"
            disabled={busy || loading || !categories.length}
          >
            {busy
              ? "Saving record…"
              : initial
                ? "Save changes"
                : "Register asset"}
          </button>
        </div>
      </form>
    </>
  );
}
