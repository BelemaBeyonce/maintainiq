export type Site = {
  id: string;
  code: string;
  name: string;
  is_synthetic: boolean;
};
export type Organization = {
  id: string;
  name: string;
  role: string;
  is_synthetic: boolean;
  sites: Site[];
};
export type SessionContext = {
  user: { id: string; email: string; name: string };
  organizations: Organization[];
};
export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
export type Category = { id: string; code: string; name: string };
export type Location = {
  id: string;
  site_id: string;
  parent_id: string | null;
  code: string;
  name: string;
};
export type Asset = {
  id: string;
  tag: string;
  name: string;
  site_id: string;
  site_name: string;
  category_id: string;
  category_name: string;
  functional_location_id: string | null;
  location_code: string;
  parent_id: string | null;
  manufacturer: string;
  model: string;
  serial_number: string;
  status: string;
  criticality: string;
  description: string;
  archived_at: string | null;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
};
export type AssetInput = Pick<
  Asset,
  | "tag"
  | "name"
  | "site_id"
  | "category_id"
  | "functional_location_id"
  | "parent_id"
  | "manufacturer"
  | "model"
  | "serial_number"
  | "status"
  | "criticality"
  | "description"
>;
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
let csrfPending: Promise<string> | undefined;
async function csrf(): Promise<string> {
  const cookie = document.cookie
    .split("; ")
    .find((v) => v.startsWith("csrftoken="));
  if (cookie) return decodeURIComponent(cookie.slice("csrftoken=".length));
  csrfPending ||= fetch("/api/auth/csrf/", {
    credentials: "same-origin",
    cache: "no-store",
  })
    .then(async (r) => {
      if (!r.ok)
        throw new ApiError(
          r.status,
          "Unable to initialize a secure session. Retry.",
        );
      return (await r.json()).csrfToken as string;
    })
    .finally(() => {
      csrfPending = undefined;
    });
  return csrfPending;
}
function describe(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(describe).join(" ");
  if (value && typeof value === "object")
    return Object.entries(value)
      .map(([k, v]) => `${k}: ${describe(v)}`)
      .join("; ");
  return "Request failed. Please retry.";
}
export async function api<T>(
  path: string,
  tenant?: string,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method || "GET";
  const headers = new Headers(options.headers);
  if (tenant) headers.set("X-Tenant-ID", tenant);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRFToken", await csrf());
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please retry.`;
    try {
      const body = await response.json();
      message = describe(
        body.error?.details && Object.keys(body.error.details).length
          ? body.error.details
          : body.error?.message || body,
      );
    } catch {
      /* Never display raw server HTML. */
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get("content-type")?.includes("text/csv"))
    return (await response.blob()) as T;
  return (await response.json()) as T;
}
export async function all<T>(
  path: string,
  tenant: string,
  signal?: AbortSignal,
): Promise<T[]> {
  const result: T[] = [];
  for (let page = 1; page <= 100; page++) {
    const data = await api<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}page=${page}`,
      tenant,
      { signal },
    );
    result.push(...data.results);
    if (!data.next) return result;
  }
  throw new Error("Too many reference records. Narrow the selected site.");
}
