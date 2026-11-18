"use client";
import { ReferenceEditor } from "@/components/reference-editor";
import { useCallback, useEffect, useState } from "react";
import { OrganizationAdmin } from "@/components/organization-admin";
import { Shell, PageHeading, ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api, all, type Category, type Location } from "@/lib/api";
function Setup() {
  const w = useWorkspace();
  const o = w.organization;
  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [siteName, setSiteName] = useState("");
  const [siteCode, setSiteCode] = useState("");
  const [catName, setCatName] = useState("");
  const [catCode, setCatCode] = useState("");
  const [locName, setLocName] = useState("");
  const [locCode, setLocCode] = useState("");
  const [locSite, setLocSite] = useState("");
  const [parent, setParent] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("technician");
  const [siteIds, setSiteIds] = useState<string[]>([]);
  const [inviteLink, setInviteLink] = useState("");
  const load = useCallback(async () => {
    if (!o) return;
    const [cats, locs] = await Promise.all([
      all<Category>("categories/", o.id),
      all<Location>("locations/", o.id),
    ]);
    setCategories(cats);
    setLocations(locs);
  }, [o]);
  useEffect(() => {
    setCategories([]);
    setLocations([]);
    setSiteIds([]);
    setInviteLink("");
    setLocSite("");
    setError("");
    void load().catch((e) => setError(e.message));
  }, [load]);
  async function create(kind: string, body: unknown) {
    if (!o) return;
    setBusy(kind);
    setError("");
    setMessage("");
    try {
      await api(`${kind}/`, o.id, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage("Record created successfully.");
      await load();
      if (kind === "sites") {
        await w.reload();
        setSiteName("");
        setSiteCode("");
      }
      if (kind === "categories") {
        setCatName("");
        setCatCode("");
      }
      if (kind === "locations") {
        setLocName("");
        setLocCode("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create record");
    } finally {
      setBusy("");
    }
  }
  if (o && !["admin", "manager"].includes(o.role))
    return (
      <section className="panel">
        <h1>Access management is restricted</h1>
        <p>Your current role cannot configure the organization.</p>
      </section>
    );
  return (
    <>
      <PageHeading
        eyebrow="ORGANIZATION / CONTROLLED ACCESS"
        title="Organization & access"
        description="Keep site boundaries explicit. Invite team members with only the access they need."
      />
      <ErrorNotice error={error} />
      {message && (
        <p className="success-notice" role="status">
          {message}
        </p>
      )}
      <div className="setup-grid">
        <OrganizationAdmin />
        <section className="panel">
          <span className="eyebrow">INVITATION-ONLY ONBOARDING</span>
          <h2>Invite a team member</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!o) return;
              setBusy("invite");
              setError("");
              setInviteLink("");
              try {
                const result = await api<{ accept_url?: string }>(
                  "invitations/",
                  o.id,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      email,
                      role,
                      site_ids: role === "admin" ? [] : siteIds,
                    }),
                  },
                );
                setInviteLink(result.accept_url || "");
                setMessage(
                  result.accept_url
                    ? "Development invitation created. Share this private link only with the intended recipient."
                    : "Invitation sent by email.",
                );
                setEmail("");
              } catch (e) {
                setError(e instanceof Error ? e.message : "Invitation failed");
              } finally {
                setBusy("");
              }
            }}
          >
            <label>
              Email address
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Assigned role
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {(o?.role === "admin"
                  ? [
                      "admin",
                      "manager",
                      "engineer",
                      "technician",
                      "requester",
                      "auditor",
                    ]
                  : ["engineer", "technician", "requester", "auditor"]
                ).map((r) => (
                  <option value={r} key={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            {role !== "admin" ? (
              <fieldset>
                <legend>Permitted sites *</legend>
                {o?.sites.map((site) => (
                  <label className="checkbox-label" key={site.id}>
                    <input
                      type="checkbox"
                      checked={siteIds.includes(site.id)}
                      onChange={(e) =>
                        setSiteIds((current) =>
                          e.target.checked
                            ? [...current, site.id]
                            : current.filter((id) => id !== site.id),
                        )
                      }
                    />
                    {site.name}
                  </label>
                ))}
              </fieldset>
            ) : (
              <p>
                Administrators can access every site in their own organization.
              </p>
            )}
            <button className="button primary" disabled={!!busy}>
              {busy === "invite" ? "Creating invitation…" : "Create invitation"}
            </button>
          </form>
          {inviteLink && (
            <label className="invite-link">
              Private development invitation
              <input
                aria-label="Private invitation link"
                readOnly
                value={inviteLink}
                onFocus={(e) => e.target.select()}
              />
              <small>
                Expires in 24 hours. This bearer link grants the assigned
                access; do not post it publicly.
              </small>
            </label>
          )}
        </section>
        <section className="panel">
          <span className="eyebrow">YOUR AUTHORIZED SCOPE</span>
          <h2>Sites & equipment categories</h2>
          <h3>Sites</h3>
          <ul className="reference-list">
            {o?.sites.map((site) => (
              <li key={site.id}>
                <strong>{site.name}</strong>
                <small>{site.code}</small>
                <ReferenceEditor
                  key={`${site.id}-${site.name}`}
                  kind="sites"
                  record={site}
                  onSaved={w.reload}
                />
              </li>
            ))}
          </ul>
          <h3>Categories</h3>
          <ul className="reference-list">
            {categories.map((category) => (
              <li key={category.id}>
                {category.name}
                <small>{category.code}</small>
                <ReferenceEditor
                  key={`${category.id}-${category.name}`}
                  kind="categories"
                  record={category}
                  onSaved={load}
                />
              </li>
            ))}
          </ul>
          <h3>Functional locations</h3>
          <ul className="reference-list">
            {locations.map((location) => (
              <li key={location.id}>
                {location.name}
                <small>{location.code}</small>
                <ReferenceEditor
                  key={`${location.id}-${location.name}`}
                  kind="locations"
                  record={location}
                  onSaved={load}
                />
              </li>
            ))}
          </ul>
        </section>
        {o?.role === "admin" && (
          <>
            <section className="panel">
              <h2>Add a site</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void create("sites", { code: siteCode, name: siteName });
                }}
              >
                <label>
                  Site code
                  <input
                    required
                    maxLength={40}
                    value={siteCode}
                    onChange={(e) => setSiteCode(e.target.value)}
                  />
                </label>
                <label>
                  Site name
                  <input
                    required
                    maxLength={160}
                    value={siteName}
                    onChange={(e) => setSiteName(e.target.value)}
                  />
                </label>
                <button className="button primary" disabled={!!busy}>
                  Create site
                </button>
              </form>
            </section>
            <section className="panel">
              <h2>Add an asset category</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void create("categories", { code: catCode, name: catName });
                }}
              >
                <label>
                  Category code
                  <input
                    required
                    pattern="[-a-zA-Z0-9_]+"
                    maxLength={50}
                    value={catCode}
                    onChange={(e) => setCatCode(e.target.value)}
                  />
                </label>
                <label>
                  Category name
                  <input
                    required
                    maxLength={100}
                    value={catName}
                    onChange={(e) => setCatName(e.target.value)}
                  />
                </label>
                <button className="button primary" disabled={!!busy}>
                  Create category
                </button>
              </form>
            </section>
            <section className="panel">
              <h2>Add a functional location</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void create("locations", {
                    code: locCode,
                    name: locName,
                    site_id: locSite,
                    parent_id: parent || null,
                  });
                }}
              >
                <label>
                  Location code
                  <input
                    required
                    maxLength={60}
                    value={locCode}
                    onChange={(e) => setLocCode(e.target.value)}
                  />
                </label>
                <label>
                  Location name
                  <input
                    required
                    maxLength={160}
                    value={locName}
                    onChange={(e) => setLocName(e.target.value)}
                  />
                </label>
                <label>
                  Site
                  <select
                    required
                    aria-label="Location site"
                    value={locSite}
                    onChange={(e) => {
                      setLocSite(e.target.value);
                      setParent("");
                    }}
                  >
                    <option value="">Select a site</option>
                    {o.sites.map((site) => (
                      <option key={site.id} value={site.id}>
                        {site.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Parent location
                  <select
                    value={parent}
                    onChange={(e) => setParent(e.target.value)}
                  >
                    <option value="">Top-level location</option>
                    {locations
                      .filter((location) => location.site_id === locSite)
                      .map((location) => (
                        <option key={location.id} value={location.id}>
                          {location.code} · {location.name}
                        </option>
                      ))}
                  </select>
                </label>
                <button className="button primary" disabled={!!busy}>
                  Create location
                </button>
              </form>
            </section>
          </>
        )}
      </div>
    </>
  );
}
export default function Page() {
  const { organization } = useWorkspace();
  return (
    <Shell>
      <Setup key={organization?.id} />
    </Shell>
  );
}
