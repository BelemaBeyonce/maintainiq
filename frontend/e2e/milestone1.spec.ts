import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";

const credentials: Record<string, string> = JSON.parse(
  readFileSync(
    process.env.DEMO_CREDENTIALS_FILE || "../demo-credentials.json",
    "utf8",
  ).replace(/^\uFEFF/, ""),
);
const email = (role: string, org = "a") =>
  `${role}.${org}@synthetic.maintainiq.test`;
async function loginAccount(page: Page, address: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(address);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "A clearer view of your assets." }),
  ).toBeVisible();
}
async function login(page: Page, role: string, org = "a") {
  await loginAccount(page, email(role, org), credentials[email(role, org)]);
}
async function csrf(request: APIRequestContext) {
  const result = await request.get("/api/auth/csrf/");
  return (await result.json()).csrfToken as string;
}
const suffix = randomBytes(4).toString("hex");
let assetId = "";
const tag = `E2E-P-${suffix}`;

test.describe.serial("Milestone 1 live acceptance", () => {
  test("Organization A manager registers, edits, archives and reads retained pump history", async ({
    page,
  }) => {
    await login(page, "manager");
    await page.getByRole("link", { name: "Asset registry" }).click();
    await page.getByRole("link", { name: "+ Register asset" }).click();
    await page.getByLabel("Asset tag *").fill(tag);
    await page
      .getByLabel("Asset name *")
      .fill(`Synthetic acceptance pump ${suffix}`);
    await page
      .getByLabel("Category *")
      .selectOption({ label: "Centrifugal pumps" });
    await page
      .getByLabel("Manufacturer", { exact: true })
      .fill("Synthetic acceptance manufacturer");
    await page
      .getByRole("button", { name: "Register asset", exact: true })
      .click();
    await expect(page).toHaveURL(/\/assets\/[0-9a-f-]{36}$/);
    assetId = page.url().split("/").pop()!;
    await expect(
      page.getByRole("heading", {
        name: `Synthetic acceptance pump ${suffix}`,
      }),
    ).toBeVisible();
    await expect(
      page.getByText("Asset created", { exact: true }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Edit record" }).click();
    await page.getByLabel("Serial number").fill(`SYN-E2E-${suffix}`);
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(
      page.getByText("Asset updated", { exact: true }),
    ).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page
      .getByRole("button", { name: "Archive asset", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Archived");
    await expect(
      page.getByText("Asset archived", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Asset created", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit record" })).toHaveCount(
      0,
    );
    await page
      .getByRole("link", { name: "Asset registry", exact: true })
      .click();
    await page.getByLabel("Search equipment").fill(tag);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(
      page.getByText("No matching equipment.", { exact: false }),
    ).toBeVisible();
    await page.getByLabel("Include archived").check();
    await expect(
      page.getByRole("link", { name: `Synthetic acceptance pump ${suffix}` }),
    ).toBeVisible();
    await page.screenshot({
      path: "../docs/screenshots/asset-registry.png",
      fullPage: true,
    });
  });

  test("Organization B cannot read A's asset, history, mutations, dashboard or export", async ({
    page,
  }) => {
    await login(page, "manager", "b");
    const context = await (await page.request.get("/api/auth/context/")).json();
    const b = context.organizations[0].id;
    const headers = {
      "X-Tenant-ID": b,
      "X-CSRFToken": await csrf(page.request),
    };
    for (const url of [
      `/api/assets/${assetId}/?include_archived=true`,
      `/api/assets/${assetId}/history/?include_archived=true`,
    ]) {
      expect((await page.request.get(url, { headers })).status()).toBe(404);
    }
    expect(
      (
        await page.request.patch(`/api/assets/${assetId}/`, {
          headers,
          data: { name: "Overwrite" },
        })
      ).status(),
    ).toBe(404);
    expect(
      await (
        await page.request.get("/api/assets/export/?include_archived=true", {
          headers,
        })
      ).text(),
    ).not.toContain(tag);
    const data = await (
      await page.request.get("/api/assets/?include_archived=true", { headers })
    ).json();
    expect(
      data.results.some((record: { id: string }) => record.id === assetId),
    ).toBe(false);
    await page.goto(`/assets/${assetId}`);
    await expect(page.getByRole("alert")).toBeVisible();
  });

  test("Technician can read permitted assets but cannot administer or change the registry", async ({
    page,
  }) => {
    await login(page, "technician");
    await expect(
      page.getByRole("link", { name: /Organization & access/ }),
    ).toHaveCount(0);
    await page.goto("/assets/new");
    await expect(
      page.getByRole("heading", { name: "Registry changes require a manager" }),
    ).toBeVisible();
    const context = await (await page.request.get("/api/auth/context/")).json();
    const headers = {
      "X-Tenant-ID": context.organizations[0].id,
      "X-CSRFToken": await csrf(page.request),
    };
    expect(
      (
        await page.request.post("/api/sites/", {
          headers,
          data: { code: "UNAUTHORIZED", name: "Unauthorized" },
        })
      ).status(),
    ).toBe(403);
    expect(
      (
        await page.request.post("/api/invitations/", {
          headers,
          data: { email: "bad@example.com", role: "admin", site_ids: [] },
        })
      ).status(),
    ).toBe(403);
  });

  test("Admin configures sites, categories and hierarchy, then onboards a site-limited technician", async ({
    page,
    browser,
  }) => {
    await login(page, "admin");
    await page.getByRole("link", { name: /Organization & access/ }).click();
    await page.getByLabel("Site code", { exact: true }).fill(`SYN-${suffix}`);
    await page
      .getByLabel("Site name", { exact: true })
      .fill(`Synthetic acceptance site ${suffix}`);
    await page
      .getByRole("button", { name: "Create site", exact: true })
      .click();
    await expect(
      page
        .getByLabel("Site", { exact: true })
        .first()
        .getByRole("option", { name: `Synthetic acceptance site ${suffix}` }),
    ).toHaveCount(1);
    await page.getByLabel("Category code").fill(`test-${suffix}`);
    await page
      .getByLabel("Category name")
      .fill(`Synthetic test category ${suffix}`);
    await page
      .getByRole("button", { name: "Create category", exact: true })
      .click();
    await expect(
      page
        .locator(".reference-list li")
        .filter({ hasText: `Synthetic test category ${suffix}` }),
    ).toBeVisible();
    const locationPanel = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Add a functional location" }),
    });
    await locationPanel.getByLabel("Location code").fill(`AREA-${suffix}`);
    await locationPanel
      .getByLabel("Location name")
      .fill(`Synthetic location ${suffix}`);
    await locationPanel
      .getByLabel("Location site", { exact: true })
      .selectOption({ label: `Synthetic acceptance site ${suffix}` });
    await locationPanel
      .getByRole("button", { name: "Create location", exact: true })
      .click();
    await expect(
      page
        .locator(".reference-list li")
        .filter({ hasText: `Synthetic location ${suffix}` }),
    ).toBeVisible();
    const invitePanel = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Invite a team member" }),
    });
    const invitedEmail = `synthetic-${suffix}@example.com`,
      password = randomBytes(20).toString("hex");
    await invitePanel.getByLabel("Email address").fill(invitedEmail);
    await invitePanel
      .getByLabel(`Synthetic acceptance site ${suffix}`, { exact: true })
      .check();
    await invitePanel
      .getByRole("button", { name: "Create invitation", exact: true })
      .click();
    const link = await invitePanel
      .getByLabel("Private invitation link")
      .inputValue();
    const context = await browser.newContext();
    const invited = await context.newPage();
    await invited.goto(link);
    await expect(
      invited.getByText(invitedEmail, { exact: false }),
    ).toBeVisible();
    await invited.getByLabel("Full name").fill("Synthetic invited technician");
    await invited.getByLabel("Password", { exact: true }).fill(password);
    await invited
      .getByRole("button", { name: "Accept invitation", exact: true })
      .click();
    await expect(invited.getByRole("status")).toContainText(
      "Invitation accepted",
    );
    await invited.getByRole("link", { name: "Go to sign in" }).click();
    await invited.getByLabel("Email address").fill(invitedEmail);
    await invited.getByLabel("Password", { exact: true }).fill(password);
    await invited.getByRole("button", { name: "Sign in →" }).click();
    await expect(invited).toHaveURL(/\/dashboard$/);
    const userContext = await (
      await invited.request.get("/api/auth/context/")
    ).json();
    expect(userContext.organizations[0].sites).toHaveLength(1);
    expect(userContext.organizations[0].sites[0].name).toBe(
      `Synthetic acceptance site ${suffix}`,
    );
    await context.close();
  });

  test("An explicitly invited existing account can switch organizations without mixing their scopes", async ({
    page,
  }) => {
    const switchEmail = `synthetic-switch-${suffix}@example.com`;
    const switchPassword = randomBytes(20).toString("hex");
    await login(page, "admin");
    const aContext = await (
      await page.request.get("/api/auth/context/")
    ).json();
    const a = aContext.organizations[0];
    const initialInvite = await page.request.post("/api/invitations/", {
      headers: { "X-Tenant-ID": a.id, "X-CSRFToken": await csrf(page.request) },
      data: {
        email: switchEmail,
        role: "manager",
        site_ids: [
          a.sites.find((site: { code: string }) => site.code === "SYN-OG").id,
        ],
      },
    });
    expect(initialInvite.status()).toBe(201);
    const firstToken = new URL(
      (await initialInvite.json()).accept_url,
    ).hash.split("token=")[1];
    expect(
      (
        await page.request.post("/api/auth/invitations/accept/", {
          headers: { "X-CSRFToken": await csrf(page.request) },
          data: {
            token: firstToken,
            full_name: "Synthetic switching user",
            password: switchPassword,
          },
        })
      ).status(),
    ).toBe(201);
    await login(page, "admin", "b");
    const bContext = await (
      await page.request.get("/api/auth/context/")
    ).json();
    const b = bContext.organizations[0];
    let token = await csrf(page.request);
    const invitation = await page.request.post("/api/invitations/", {
      headers: { "X-Tenant-ID": b.id, "X-CSRFToken": token },
      data: {
        email: switchEmail,
        role: "engineer",
        site_ids: [b.sites[0].id],
      },
    });
    expect(invitation.status()).toBe(201);
    const privateToken = new URL(
      (await invitation.json()).accept_url,
    ).hash.split("token=")[1];
    await page.getByRole("button", { name: "Sign out" }).click();
    token = await csrf(page.request);
    expect(
      (
        await page.request.post("/api/auth/invitations/accept/", {
          headers: { "X-CSRFToken": token },
          data: {
            token: privateToken,
            full_name: "Synthetic existing manager",
            password: switchPassword,
          },
        })
      ).status(),
    ).toBe(201);
    await loginAccount(page, switchEmail, switchPassword);
    await page
      .getByLabel("Organization", { exact: true })
      .selectOption({ label: "Synthetic Organization B" });
    await expect(
      page
        .getByLabel("Site", { exact: true })
        .getByRole("option", { name: "Synthetic Workshop" }),
    ).toHaveCount(1);
    await page
      .getByRole("link", { name: "Asset registry", exact: true })
      .click();
    await expect(
      page
        .getByRole("cell", { name: "Synthetic Workshop", exact: true })
        .first(),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "+ Register asset" }),
    ).toHaveCount(0);
    await page
      .getByLabel("Organization", { exact: true })
      .selectOption({ label: "Synthetic Organization A" });
    await expect(
      page.getByRole("link", { name: "+ Register asset" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Overview" }).click();
    await expect(
      page.getByRole("heading", { name: "A clearer view of your assets." }),
    ).toBeVisible();
    await expect(
      page.locator(".metric").first().locator("strong"),
    ).not.toHaveText("—");
    await page.screenshot({
      path: "../docs/screenshots/dashboard.png",
      fullPage: true,
    });
  });

  test("Mobile navigation and asset list remain usable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, "auditor");
    await page
      .getByRole("link", { name: "Asset registry", exact: true })
      .click();
    await expect(page.getByLabel("Search equipment")).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: "../docs/screenshots/mobile-registry.png",
      fullPage: true,
    });
  });
});
