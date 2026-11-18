"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AssetForm } from "@/components/asset-form";
import { Shell, ErrorNotice } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
import { api, type Asset } from "@/lib/api";
function Edit() {
  const { id } = useParams<{ id: string }>();
  const { organization: o } = useWorkspace();
  const [asset, setAsset] = useState<Asset>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!o) return;
    const c = new AbortController();
    setAsset(undefined);
    setError("");
    void api<Asset>(`assets/${id}/`, o.id, { signal: c.signal })
      .then(setAsset)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [id, o]);
  return (
    <>
      <ErrorNotice error={error} />
      {asset ? (
        <AssetForm key={`${o?.id}-${id}`} initial={asset} />
      ) : (
        !error && <p>Loading equipment record…</p>
      )}
    </>
  );
}
export default function PageComponent() {
  return (
    <Shell>
      <Edit />
    </Shell>
  );
}
