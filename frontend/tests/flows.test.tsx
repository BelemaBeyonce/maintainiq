import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  all: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  reload: vi.fn(),
  signOut: vi.fn(),
  selectOrganization: vi.fn(),
  selectSite: vi.fn(),
  role: "manager",
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  usePathname: () => "/assets",
}));
vi.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => (
    <a {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/api", async () => ({
  ...(await vi.importActual("@/lib/api")),
  api: mocks.api,
  all: mocks.all,
}));
vi.mock("@/components/workspace", () => {
  const organization = {
    id: "org-a",
    name: "Synthetic A",
    get role() {
      return mocks.role;
    },
    sites: [{ id: "site-a", name: "Site A" }],
  };
  return {
    useWorkspace: () => ({
      context: {
        user: {
          id: "user-a",
          name: "Synthetic Manager",
          email: "manager@example.com",
        },
        organizations: [
          {
            id: "org-a",
            name: "Synthetic A",
            sites: [{ id: "site-a", name: "Site A" }],
          },
        ],
      },
      organization,
      siteId: "site-a",
      loading: false,
      reload: mocks.reload,
      signOut: mocks.signOut,
      selectOrganization: mocks.selectOrganization,
      selectSite: mocks.selectSite,
    }),
  };
});
import Login from "@/app/login/page";
import { AssetForm } from "@/components/asset-form";
import { Shell } from "@/components/shell";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.role = "manager";
  mocks.signOut.mockResolvedValue(undefined);
  mocks.reload.mockResolvedValue(undefined);
  mocks.api.mockResolvedValue({ id: "asset-new" });
  mocks.all.mockImplementation(async (path: string) =>
    path.startsWith("categories") ? [{ id: "category-a", name: "Pumps" }] : [],
  );
});

describe("connected forms", () => {
  it("signs in with credentials and navigates after refreshing real session context", async () => {
    const user = userEvent.setup();
    render(<Login />);
    await user.type(
      screen.getByLabelText("Email address"),
      "manager@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "synthetic-passphrase");
    await user.click(screen.getByRole("button", { name: "Sign in →" }));
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/dashboard"),
    );
    expect(mocks.reload).toHaveBeenCalled();
    expect(JSON.parse(mocks.api.mock.calls[0][2].body)).toEqual({
      email: "manager@example.com",
      password: "synthetic-passphrase",
    });
  });
  it("shows backend login failure without navigating", async () => {
    mocks.api.mockRejectedValue(new Error("Invalid email or password"));
    const user = userEvent.setup();
    render(<Login />);
    await user.type(
      screen.getByLabelText("Email address"),
      "manager@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in →" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password",
    );
    expect(mocks.replace).not.toHaveBeenCalled();
  });
  it("registers an asset through the tenant-scoped API and opens its saved record", async () => {
    const user = userEvent.setup();
    render(<AssetForm />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Register asset" }),
      ).toBeEnabled(),
    );
    await user.type(screen.getByLabelText("Asset tag *"), "P-202");
    await user.type(screen.getByLabelText("Asset name *"), "Synthetic pump");
    await user.click(screen.getByRole("button", { name: "Register asset" }));
    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/assets/asset-new"),
    );
    const [path, tenant, options] = mocks.api.mock.calls[0];
    expect(path).toBe("assets/");
    expect(tenant).toBe("org-a");
    expect(JSON.parse(options.body)).toMatchObject({
      site_id: "site-a",
      category_id: "category-a",
      tag: "P-202",
      name: "Synthetic pump",
    });
  });
  it("preserves entered asset data and displays server validation errors", async () => {
    mocks.api.mockRejectedValue(new Error("Asset tag already exists"));
    const user = userEvent.setup();
    render(<AssetForm />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Register asset" }),
      ).toBeEnabled(),
    );
    await user.type(screen.getByLabelText("Asset tag *"), "P-101");
    await user.type(screen.getByLabelText("Asset name *"), "Synthetic pump");
    await user.click(screen.getByRole("button", { name: "Register asset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Asset tag already exists",
    );
    expect(screen.getByLabelText("Asset tag *")).toHaveValue("P-101");
  });
  it("does not offer registry writes to technicians", () => {
    mocks.role = "technician";
    render(<AssetForm />);
    expect(
      screen.getByRole("heading", {
        name: "Registry changes require a manager",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Register asset" }),
    ).not.toBeInTheDocument();
  });
});

describe("workspace navigation", () => {
  it("uses real routes and organization/site selection handlers", () => {
    render(
      <Shell>
        <h1>Asset content</h1>
      </Shell>,
    );
    expect(
      screen.getByRole("link", { name: /Asset registry/ }),
    ).toHaveAttribute("href", "/assets");
    expect(
      screen.getByRole("link", { name: /Organization & access/ }),
    ).toHaveAttribute("href", "/organization");
    fireEvent.change(screen.getByLabelText("Site"), {
      target: { value: "site-a" },
    });
    expect(mocks.selectSite).toHaveBeenCalledWith("site-a");
    fireEvent.change(screen.getByLabelText("Organization"), {
      target: { value: "org-a" },
    });
    expect(mocks.selectOrganization).toHaveBeenCalledWith("org-a");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(mocks.signOut).toHaveBeenCalled();
  });
  it("hides administrative navigation from technicians", () => {
    mocks.role = "technician";
    render(
      <Shell>
        <p>Authorized content</p>
      </Shell>,
    );
    expect(
      screen.queryByRole("link", { name: /Organization & access/ }),
    ).not.toBeInTheDocument();
  });
});
