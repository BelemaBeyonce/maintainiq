"use client";
import { AssetForm } from "@/components/asset-form";
import { Shell } from "@/components/shell";
import { useWorkspace } from "@/components/workspace";
export default function Page() {
  const { organization, siteId } = useWorkspace();
  return (
    <Shell>
      <AssetForm key={`${organization?.id}-${siteId}`} />
    </Shell>
  );
}
