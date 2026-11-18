"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/auth-card";
import { ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api } from "@/lib/api";
export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const w = useWorkspace();
  const router = useRouter();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("auth/login/", undefined, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await w.reload();
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthCard
      title="Sign in to your workspace"
      subtitle="Use the account invited by your organization."
    >
      <form onSubmit={submit}>
        <ErrorNotice error={error} />
        <label>
          Email address
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <Link className="text-link" href="/forgot-password">
          Forgot your password?
        </Link>
        <button className="button primary full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in →"}
        </button>
      </form>
      <p className="auth-help">
        New to the team? Open the private invitation link from your
        administrator. Roles cannot be self-selected.
      </p>
    </AuthCard>
  );
}
