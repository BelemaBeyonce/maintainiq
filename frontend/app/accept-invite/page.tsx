"use client";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { AuthCard } from "@/components/auth-card";
import { ErrorNotice } from "@/components/shell";
import { api } from "@/lib/api";
export default function Accept() {
  const [token, setToken] = useState("");
  const [invitation, setInvitation] = useState<{
    organization: string;
    email: string;
    role: string;
  }>();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const value = new URLSearchParams(location.hash.slice(1)).get("token");
    if (!value) {
      setError("Open the complete private invitation link.");
      return;
    }
    setToken(value);
    void api<{ organization: string; email: string; role: string }>(
      "auth/invitations/inspect/",
      undefined,
      { method: "POST", body: JSON.stringify({ token: value }) },
    )
      .then(setInvitation)
      .catch((e) => setError(e.message));
    history.replaceState(null, "", location.pathname);
  }, []);
  return (
    <AuthCard
      title="Join your organization"
      subtitle="Your access is assigned by an authorized administrator."
    >
      <ErrorNotice error={error} />
      {invitation && (
        <p className="scope-summary">
          <strong>{invitation.organization}</strong>
          <br />
          {invitation.email} · {invitation.role}
        </p>
      )}
      {done ? (
        <p role="status" className="success-notice">
          Invitation accepted. Sign in to open your workspace.
        </p>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api("auth/invitations/accept/", undefined, {
                method: "POST",
                body: JSON.stringify({ token, full_name: name, password }),
              });
              setDone(true);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Invitation failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Full name
            <input
              required
              maxLength={150}
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              required
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <small>
            If you already have an account, use its current password to verify
            your identity.
          </small>
          <button
            className="button primary full"
            disabled={busy || !invitation}
          >
            {busy ? "Joining…" : "Accept invitation"}
          </button>
        </form>
      )}
      <Link className="text-link" href="/login">
        Go to sign in
      </Link>
    </AuthCard>
  );
}
