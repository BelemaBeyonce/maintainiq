import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; Max-Age=0; path=/";
});
describe("HTTP client boundaries", () => {
  it("sends tenant and CSRF headers with same-origin cookies", async () => {
    document.cookie = "csrftoken=synthetic-csrf-token; path=/";
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "saved" }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetch);
    await api("assets/", "org-a", {
      method: "POST",
      body: JSON.stringify({ tag: "P-202" }),
    });
    const [url, request] = fetch.mock.calls[0];
    expect(url).toBe("/api/assets/");
    expect(request.credentials).toBe("same-origin");
    expect(request.headers.get("X-Tenant-ID")).toBe("org-a");
    expect(request.headers.get("X-CSRFToken")).toBe("synthetic-csrf-token");
    expect(request.headers.has("Authorization")).toBe(false);
  });
  it("fetches an initial CSRF token before mutations", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: "issued-token" })),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await api("auth/logout/", undefined, { method: "POST", body: "{}" });
    expect(fetch.mock.calls[0][0]).toBe("/api/auth/csrf/");
    expect(fetch.mock.calls[1][1].headers.get("X-CSRFToken")).toBe(
      "issued-token",
    );
  });
  it("returns field errors without rendering server HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ error: { details: { tag: ["Already exists"] } } }),
            { status: 400 },
          ),
        ),
    );
    await expect(api("assets/", "org-a")).rejects.toThrow(
      "tag: Already exists",
    );
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("<script>private stack</script>", { status: 500 }),
        ),
    );
    await expect(api("assets/", "org-a")).rejects.toThrow(
      "Request failed (500)",
    );
    expect(ApiError.prototype).toBeInstanceOf(Error);
  });
});
