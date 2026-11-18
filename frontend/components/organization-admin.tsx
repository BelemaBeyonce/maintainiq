"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useWorkspace } from "./workspace";
import { ErrorNotice } from "./shell";

type Profile = { name: string; timezone: string; currency: string };
type Member = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  site_ids: string[];
};
export function OrganizationAdmin() {
  const { organization, reload } = useWorkspace();
  const [profile, setProfile] = useState<Profile>();
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!organization || organization.role !== "admin") return;
      const [data, people] = await Promise.all([
        api<Profile>("organization/", organization.id, { signal }),
        api<Member[]>("memberships/", organization.id, { signal }),
      ]);
      setProfile(data);
      setMembers(people);
    },
    [organization],
  );
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).catch((e) => {
      if (!controller.signal.aborted) setError(e.message);
    });
    return () => controller.abort();
  }, [load]);
  if (!organization || organization.role !== "admin") return null;
  return (
    <>
      <section className="panel">
        <h2>Organization profile</h2>
        <p className="muted">
          The synthetic label cannot be removed through this form.
        </p>
        <ErrorNotice error={error} />
        {message && (
          <p role="status" className="success-notice">
            {message}
          </p>
        )}
        {profile && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api("organization/", organization.id, {
                  method: "PATCH",
                  body: JSON.stringify(profile),
                });
                setMessage("Organization profile saved.");
                await reload();
              } catch (e) {
                setError(
                  e instanceof Error
                    ? e.message
                    : "Unable to save organization",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Organization name
              <input
                required
                maxLength={160}
                value={profile.name}
                onChange={(e) =>
                  setProfile({ ...profile, name: e.target.value })
                }
              />
            </label>
            <label>
              Timezone
              <input
                required
                value={profile.timezone}
                onChange={(e) =>
                  setProfile({ ...profile, timezone: e.target.value })
                }
                placeholder="Africa/Lagos"
              />
            </label>
            <label>
              Currency
              <input
                required
                pattern="[A-Z]{3}"
                maxLength={3}
                value={profile.currency}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    currency: e.target.value.toUpperCase(),
                  })
                }
              />
            </label>
            <button className="button primary" disabled={busy}>
              Save organization profile
            </button>
          </form>
        )}
      </section>
      <section className="panel">
        <h2>Membership permissions</h2>
        <p className="muted">
          Changes apply server-side on the next request. Administrators cannot
          remove their own access.
        </p>
        {members.map((member) => (
          <MemberEditor
            key={member.id}
            member={member}
            onSaved={() => load()}
          />
        ))}
        {members.length === 0 && <p>No memberships available.</p>}
      </section>
    </>
  );
}
function MemberEditor({
  member,
  onSaved,
}: {
  member: Member;
  onSaved: () => Promise<void>;
}) {
  const { organization } = useWorkspace();
  const [form, setForm] = useState(member);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="member-editor"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!organization) return;
        setBusy(true);
        setSaved(false);
        setError("");
        try {
          await api(`memberships/${member.id}/`, organization.id, {
            method: "PATCH",
            body: JSON.stringify({
              role: form.role,
              is_active: form.is_active,
              site_ids: form.role === "admin" ? [] : form.site_ids,
            }),
          });
          setSaved(true);
          await onSaved();
        } catch (e) {
          setError(e instanceof Error ? e.message : "Unable to change access");
        } finally {
          setBusy(false);
        }
      }}
    >
      <strong>{member.email}</strong>
      <ErrorNotice error={error} />
      <label>
        Role for {member.email}
        <select
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value })}
        >
          {[
            "admin",
            "manager",
            "engineer",
            "technician",
            "requester",
            "auditor",
          ].map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
      </label>
      {form.role !== "admin" && (
        <fieldset>
          <legend>Site access for {member.email}</legend>
          {organization?.sites.map((site) => (
            <label className="checkbox-label" key={site.id}>
              <input
                type="checkbox"
                checked={form.site_ids.includes(site.id)}
                onChange={(e) =>
                  setForm({
                    ...form,
                    site_ids: e.target.checked
                      ? [...form.site_ids, site.id]
                      : form.site_ids.filter((id) => id !== site.id),
                  })
                }
              />
              {site.name}
            </label>
          ))}
        </fieldset>
      )}
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
        />
        Active membership
      </label>
      <button className="button secondary compact" disabled={busy}>
        {busy ? "Saving…" : "Save access"}
      </button>
      {saved && (
        <span role="status" className="muted">
          {" "}
          Access saved.
        </span>
      )}
    </form>
  );
}
