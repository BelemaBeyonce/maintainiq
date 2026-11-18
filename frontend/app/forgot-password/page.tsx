"use client";
import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/auth-card";
import { ErrorNotice } from "@/components/shell";
import { api } from "@/lib/api";
export default function Forgot() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <AuthCard
      title="Reset your password"
      subtitle="We will send instructions if your account exists."
    >
      {done ? (
        <p role="status" className="success-notice">
          If the account exists, reset instructions will be sent. Check your
          organization email.
        </p>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api("auth/password-reset/", undefined, {
                method: "POST",
                body: JSON.stringify({ email }),
              });
              setDone(true);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Request failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <ErrorNotice error={error} />
          <label>
            Email address
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <button className="button primary full" disabled={busy}>
            {busy ? "Requesting…" : "Send reset instructions"}
          </button>
        </form>
      )}
      <Link className="text-link" href="/login">
        Back to sign in
      </Link>
    </AuthCard>
  );
}
