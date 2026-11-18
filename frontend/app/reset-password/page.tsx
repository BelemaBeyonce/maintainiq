"use client";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { AuthCard } from "@/components/auth-card";
import { ErrorNotice } from "@/components/shell";
import { api } from "@/lib/api";
export default function Reset() {
  const [parts, setParts] = useState<{ uid: string; token: string }>();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const p = new URLSearchParams(location.hash.slice(1));
    const uid = p.get("uid"),
      token = p.get("token");
    if (uid && token) setParts({ uid, token });
    else setError("Open the complete private reset link from your email.");
    history.replaceState(null, "", location.pathname);
  }, []);
  return (
    <AuthCard
      title="Choose a new password"
      subtitle="Use at least 12 characters and a unique passphrase."
    >
      {done ? (
        <p role="status" className="success-notice">
          Password changed. You can now sign in.
        </p>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api("auth/password-reset/confirm/", undefined, {
                method: "POST",
                body: JSON.stringify({ ...parts, password }),
              });
              setDone(true);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Reset failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <ErrorNotice error={error} />
          <label>
            New password
            <input
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="button primary full" disabled={busy || !parts}>
            {busy ? "Saving…" : "Save new password"}
          </button>
        </form>
      )}
      <Link className="text-link" href="/login">
        Back to sign in
      </Link>
    </AuthCard>
  );
}
