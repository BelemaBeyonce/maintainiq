"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api, type Organization, type SessionContext } from "@/lib/api";

type Workspace = {
  context: SessionContext | null;
  organization?: Organization;
  siteId: string;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  selectOrganization: (id: string) => void;
  selectSite: (id: string) => void;
  signOut: () => Promise<void>;
};
const Context = createContext<Workspace | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<SessionContext | null>(null);
  const [tenantId, setTenant] = useState("");
  const [siteId, setSite] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const router = useRouter();
  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api<SessionContext>("auth/context/");
      setContext(data);
      const stored = localStorage.getItem("maintainiq.organization");
      const chosen =
        data.organizations.find((o) => o.id === stored) ||
        data.organizations[0];
      setTenant(chosen?.id || "");
      setSite("");
    } catch (e) {
      setContext(null);
      if (!(e instanceof Error) || !e.message.includes("Authentication"))
        setError(
          e instanceof Error ? e.message : "Unable to load your workspace",
        );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);
  function selectOrganization(id: string) {
    setTenant(id);
    setSite("");
    localStorage.setItem("maintainiq.organization", id);
  }
  function selectSite(id: string) {
    setSite(id);
  }
  async function signOut() {
    try {
      await api("auth/logout/", undefined, { method: "POST", body: "{}" });
    } finally {
      setContext(null);
      localStorage.removeItem("maintainiq.organization");
      router.replace("/login");
    }
  }
  return (
    <Context.Provider
      value={{
        context,
        organization: context?.organizations.find((o) => o.id === tenantId),
        siteId,
        loading,
        error,
        reload,
        selectOrganization,
        selectSite,
        signOut,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("WorkspaceProvider required");
  return value;
}
