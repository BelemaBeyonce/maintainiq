"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useWorkspace } from "./workspace";
import { ErrorNotice } from "./shell";
export function ReferenceEditor({
  kind,
  record,
  onSaved,
}: {
  kind: "sites" | "categories" | "locations";
  record: { id: string; code: string; name: string };
  onSaved: () => Promise<void>;
}) {
  const { organization } = useWorkspace();
  const [code, setCode] = useState(record.code);
  const [name, setName] = useState(record.name);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (organization?.role !== "admin") return null;
  return (
    <details className="reference-editor">
      <summary>Edit {record.code}</summary>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api(`${kind}/${record.id}/`, organization.id, {
              method: "PATCH",
              body: JSON.stringify({ code, name }),
            });
            await onSaved();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Update failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorNotice error={error} />
        <label>
          Code for {record.code}
          <input
            required
            maxLength={kind === "sites" ? 40 : kind === "categories" ? 50 : 60}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </label>
        <label>
          Name for {record.code}
          <input
            required
            maxLength={kind === "categories" ? 100 : 160}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <button className="button secondary compact" disabled={busy}>
          {busy ? "Saving…" : "Save reference record"}
        </button>
      </form>
    </details>
  );
}
