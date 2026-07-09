import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const diagnostics = vi.fn();
const grant = vi.fn((_id: string, _perms: string[]) => Promise.resolve({ name: "Hello Plugin" }));
const disable = vi.fn((_id: string) => Promise.resolve({}));
const enable = vi.fn((_id: string) => Promise.resolve({}));
const revoke = vi.fn((_id: string, _perms: string[]) => Promise.resolve({ name: "Hello Plugin" }));
const uninstall = vi.fn((_id: string) => Promise.resolve({ plugin_id: _id, removed: true }));
const installPlugin = vi.fn((_file: File) => Promise.resolve({ plugin: { name: "X" }, outcome: "unsigned" }));
const marketplaceList = vi.fn().mockResolvedValue({ configured: false, plugins: [], revoked_installed: [] });
const marketplaceInstall = vi.fn((_id: string) => Promise.resolve({}));
const activateLicense = vi.fn((_id: string, _token: unknown) =>
  Promise.resolve({ plugin_id: _id, valid: true, license_type: "pro", expires_at: null, reason: "licensed" }),
);
const removeLicense = vi.fn((_id: string) =>
  Promise.resolve({ plugin_id: _id, valid: false, license_type: null, expires_at: null, reason: "no license token found" }),
);

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  pluginsApi: {
    diagnostics: () => diagnostics(),
    grant: (id: string, perms: string[]) => grant(id, perms),
    disable: (id: string) => disable(id),
    enable: (id: string) => enable(id),
    revoke: (id: string, perms: string[]) => revoke(id, perms),
    uninstall: (id: string) => uninstall(id),
    install: (file: File) => installPlugin(file),
    license: (id: string) =>
      Promise.resolve({ plugin_id: id, valid: true, license_type: null, expires_at: null, reason: "no license provider" }),
    activateLicense: (id: string, token: unknown) => activateLicense(id, token),
    removeLicense: (id: string) => removeLicense(id),
  },
  marketplaceApi: {
    list: () => marketplaceList(),
    install: (id: string) => marketplaceInstall(id),
  },
}));

import { TooltipProvider } from "@/components/ui/tooltip";
import { useToastStore } from "@/stores/toastStore";
import { PluginsPage } from "../PluginsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TooltipProvider>
          <PluginsPage />
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const PENDING = {
  id: "community.hello",
  name: "Hello Plugin",
  version: "0.1.0",
  publisher: "community",
  description: "Adds a greeting node.",
  source: "dir:hello",
  status: "needs_permissions" as const,
  status_detail: "",
  capabilities: ["node.hello"],
  permissions: ["network"],
  granted_permissions: [],
  missing_permissions: ["network"],
  signature: "unsigned",
  official: false,
  nodes: ["hello.greeting"],
  node_categories: { "hello.greeting": "columns" },
  uninstallable: false,
  license: "community",
  trust: "community",
  ciaren_spec: ">=0.1",
  dependencies: ["requests>=2"],
  entrypoint: "hello_plugin:HelloPlugin",
  install_path: "",
};

const LOADED = {
  ...PENDING,
  status: "loaded" as const,
  permissions: [],
  missing_permissions: [],
  signature: "trusted",
};

// A drop-in plugin the user approved: loaded, with the permissions it requested
// recorded as granted. Its permissions should read as active, and it can be revoked.
const LOADED_APPROVED = {
  ...PENDING,
  status: "loaded" as const,
  permissions: ["network"],
  granted_permissions: ["network"],
  missing_permissions: [],
};

describe("PluginsPage", () => {
  beforeEach(() => {
    // Mutations invalidate ["plugins"] and trigger refetches, so mocks must keep
    // resolving (mockResolvedValue, not Once) — an exhausted Once would hand
    // react-query `undefined` and taint the output with warnings.
    vi.clearAllMocks();
    marketplaceList.mockResolvedValue({ configured: false, plugins: [], revoked_installed: [] });
    useToastStore.setState({ toasts: [] });
  });

  it("shows an empty state when nothing is installed", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    renderPage();
    expect(await screen.findByText("No plugins installed")).toBeInTheDocument();
  });

  it("always shows the trust warning", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    renderPage();
    expect(await screen.findByText(/Only install plugins you trust/i)).toBeInTheDocument();
    expect(screen.getByText(/not responsible/i)).toBeInTheDocument();
  });

  it("renders a compact pending card with an inline Approve action", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [PENDING], errors: [] });
    renderPage();

    expect(await screen.findByText("Hello Plugin")).toBeInTheDocument();
    expect(screen.getByText("Needs approval")).toBeInTheDocument();
    // The security consequence stays visible without opening the details.
    expect(screen.getByText(/Not loaded until you approve/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => expect(grant).toHaveBeenCalledWith("community.hello", []));
    // A security-relevant action (running the plugin's code) gets explicit
    // positive confirmation, not just a silent status-badge change.
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.title.includes("approved"))).toBe(true),
    );
  });

  it("opens a detail dialog with permissions, nodes, and manifest details", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [PENDING], errors: [] });
    renderPage();

    await userEvent.click(await screen.findByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    // The requested permission is shown with its friendly description.
    expect(within(dialog).getByText("network")).toBeInTheDocument();
    expect(within(dialog).getByText(/Make network requests/)).toBeInTheDocument();
    expect(within(dialog).getByText(/not loaded/i)).toBeInTheDocument();
    // Contributed nodes with their palette category.
    expect(within(dialog).getByText("hello.greeting")).toBeInTheDocument();
    expect(within(dialog).getByText("Columns")).toBeInTheDocument();
    // Manifest details: dependencies, compatibility, entry point, trust tier.
    expect(within(dialog).getByText("requests>=2")).toBeInTheDocument();
    expect(within(dialog).getByText(/Ciaren >=0.1/)).toBeInTheDocument();
    expect(within(dialog).getByText("hello_plugin:HelloPlugin")).toBeInTheDocument();
    expect(within(dialog).getByText("Trust tier")).toBeInTheDocument();

    // Approving from the dialog works too.
    await userEvent.click(within(dialog).getByRole("button", { name: /Approve/i }));
    await waitFor(() => expect(grant).toHaveBeenCalledWith("community.hello", []));
  });

  it("offers Disable in the detail dialog of a loaded plugin", async () => {
    diagnostics.mockResolvedValue({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    expect(await screen.findByText("Active")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /Disable/i }));
    await waitFor(() => expect(disable).toHaveBeenCalledWith("community.hello"));
  });

  it("shows a loaded plugin's permissions as active, not 'not granted'", async () => {
    diagnostics.mockResolvedValue({ loaded: [LOADED_APPROVED], gated: [], errors: [] });
    renderPage();

    expect(await screen.findByText("Active")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    // The permission is listed…
    expect(within(dialog).getByText("network")).toBeInTheDocument();
    // …but never flagged as "(not granted)" for a plugin that is already running.
    expect(within(dialog).queryByText(/not granted/i)).not.toBeInTheDocument();
  });

  it("revokes a previously-approved plugin's permissions", async () => {
    diagnostics.mockResolvedValue({ loaded: [LOADED_APPROVED], gated: [], errors: [] });
    renderPage();

    await userEvent.click(await screen.findByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /Revoke/i }));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("community.hello", ["network"]));
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.title.includes("revoked"))).toBe(true),
    );
  });

  it("does not offer Revoke for a plugin with no granted permissions", async () => {
    diagnostics.mockResolvedValue({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    await userEvent.click(await screen.findByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: /Revoke/i })).not.toBeInTheDocument();
  });

  it("uninstalls a managed plugin after confirmation", async () => {
    diagnostics.mockResolvedValue({
      loaded: [{ ...LOADED, uninstallable: true }],
      gated: [],
      errors: [],
    });
    renderPage();

    await userEvent.click(await screen.findByText("Hello Plugin"));
    const detail = await screen.findByRole("dialog");
    await userEvent.click(within(detail).getByRole("button", { name: /Uninstall/i }));
    // A destructive confirm dialog gates the delete; nothing happens until confirmed.
    expect(uninstall).not.toHaveBeenCalled();
    const confirm = await screen.findByRole("dialog", { name: /Uninstall Hello Plugin/i });
    await userEvent.click(within(confirm).getByRole("button", { name: /Uninstall/i }));
    await waitFor(() => expect(uninstall).toHaveBeenCalledWith("community.hello"));
  });

  it("does not offer Uninstall for a dev-dir / entry-point plugin", async () => {
    diagnostics.mockResolvedValue({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    await userEvent.click(await screen.findByText("Hello Plugin"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: /Uninstall/i })).not.toBeInTheDocument();
  });

  it("shows the install-time signature trust badge", async () => {
    // Distinct ids: a plugin is either loaded or gated, and the list keys by id.
    const pendingOther = { ...PENDING, id: "community.other", name: "Other Plugin" };
    diagnostics.mockResolvedValue({ loaded: [LOADED], gated: [pendingOther], errors: [] });
    renderPage();

    // LOADED verified as trusted; PENDING was an unsigned drop-in.
    expect(await screen.findByText("Trusted")).toBeInTheDocument();
    expect(screen.getByText("Unsigned")).toBeInTheDocument();
  });

  it("shows the Official badge for a first-party plugin instead of plain Trusted", async () => {
    diagnostics.mockResolvedValue({
      loaded: [{ ...LOADED, official: true }],
      gated: [],
      errors: [],
    });
    renderPage();

    expect(await screen.findByText("Official")).toBeInTheDocument();
    expect(screen.queryByText("Trusted")).not.toBeInTheDocument();
  });

  it("surfaces load errors", async () => {
    diagnostics.mockResolvedValue({
      loaded: [],
      gated: [],
      errors: [{ source: "dir:broken", error: "bad manifest" }],
    });
    renderPage();
    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByText("dir:broken")).toBeInTheDocument();
  });

  it("uploads a selected .ciarenplugin file only after acknowledging the risk", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    renderPage();

    await screen.findByText("No plugins installed");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3])], "acme.ciarenplugin");
    await userEvent.upload(input, file);

    // A risk confirmation appears; nothing is installed until the toggle is on.
    const dialog = await screen.findByRole("dialog", { name: /Install this plugin/i });
    const confirm = within(dialog).getByRole("button", { name: /Install plugin/i });
    expect(confirm).toBeDisabled();
    expect(installPlugin).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("checkbox"));
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    await waitFor(() => expect(installPlugin).toHaveBeenCalledTimes(1));
    expect(installPlugin.mock.calls[0][0].name).toBe("acme.ciarenplugin");
  });

  it("does not install when the risk confirmation is cancelled", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    renderPage();

    await screen.findByText("No plugins installed");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File([new Uint8Array([1])], "acme.ciarenplugin"));
    const dialog = await screen.findByRole("dialog", { name: /Install this plugin/i });
    await userEvent.click(within(dialog).getByRole("button", { name: /Cancel/i }));
    expect(installPlugin).not.toHaveBeenCalled();
  });

  it("shows a configured catalog and installs an entry", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValue({
      configured: true,
      plugins: [
        {
          id: "acme.databricks",
          name: "Databricks Connector",
          version: "1.0.0",
          publisher: "acme",
          description: "Connect to Databricks.",
          license: "commercial",
          trust: "trusted",
          capabilities: ["connector.databricks"],
          permissions: ["network", "credentials"],
          ciaren_spec: ">=0.1",
          dependencies: ["databricks-sql-connector"],
          nodes: ["databricks.query"],
          node_categories: { "databricks.query": "input" },
          license_required: true,
          installed: false,
          installed_version: "",
          update_available: false,
          revoked: false,
          installable: true,
        },
      ],
      revoked_installed: [],
    });
    renderPage();

    expect(await screen.findByText("Databricks Connector")).toBeInTheDocument();
    expect(screen.getByText("databricks.query")).toBeInTheDocument();
    expect(screen.getByText("Inputs")).toBeInTheDocument();
    expect(screen.getByText("License required")).toBeInTheDocument();
    // Verified-artifact trust tier plus the manifest metadata carried by the index.
    expect(screen.getByText("Trusted")).toBeInTheDocument();
    expect(screen.getByText(">=0.1")).toBeInTheDocument();
    expect(screen.getByText("databricks-sql-connector")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Install$/i }));
    await waitFor(() => expect(marketplaceInstall).toHaveBeenCalledWith("acme.databricks"));
  });

  it("marks an already-installed catalog entry as Installed", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValue({
      configured: true,
      plugins: [
        {
          id: "acme.x",
          name: "Acme X",
          version: "1.0.0",
          publisher: "acme",
          description: "",
          license: "community",
          trust: "community",
          capabilities: [],
          permissions: [],
          ciaren_spec: "",
          dependencies: [],
          nodes: ["acme.xNode"],
          node_categories: { "acme.xNode": "plugins" },
          license_required: false,
          installed: true,
          installed_version: "1.0.0",
          update_available: false,
          revoked: false,
          installable: true,
        },
      ],
      revoked_installed: [],
    });
    renderPage();

    expect(await screen.findByText("Installed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Install$/i })).not.toBeInTheDocument();
  });

  const CATALOG_ENTRY = {
    id: "acme.x",
    name: "Acme X",
    version: "2.0.0",
    publisher: "acme",
    description: "",
    license: "community",
    trust: "community",
    capabilities: [],
    permissions: [],
    ciaren_spec: "",
    dependencies: [],
    nodes: [],
    node_categories: {},
    license_required: false,
    installed: true,
    installed_version: "1.0.0",
    update_available: true,
    revoked: false,
    installable: true,
  };

  it("offers Update when the catalog has a newer version", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValue({
      configured: true,
      plugins: [CATALOG_ENTRY],
      revoked_installed: [],
    });
    renderPage();

    // The version transition is visible and the action reads Update, not Install.
    expect(await screen.findByText(/v1\.0\.0/)).toBeInTheDocument();
    expect(screen.getByText("v2.0.0")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Update/i }));
    await waitFor(() => expect(marketplaceInstall).toHaveBeenCalledWith("acme.x"));
  });

  it("shows the Official trust tier on a catalog entry", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValue({
      configured: true,
      plugins: [{ ...CATALOG_ENTRY, installed: false, update_available: false, trust: "official" }],
      revoked_installed: [],
    });
    renderPage();

    expect(await screen.findByText("Official")).toBeInTheDocument();
  });

  it("flags revoked plugins and never offers install for them", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValue({
      configured: true,
      plugins: [{ ...CATALOG_ENTRY, update_available: false, revoked: true }],
      revoked_installed: ["acme.x"],
    });
    renderPage();

    expect(await screen.findByText(/catalog has revoked plugins/i)).toBeInTheDocument();
    expect(screen.getByText("Revoked")).toBeInTheDocument();
    // No install/update action for a revoked entry (the header "Install plugin"
    // upload button is unrelated and still present).
    expect(screen.queryByRole("button", { name: /^Install$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Update$/i })).not.toBeInTheDocument();
  });

  const NEEDS_LICENSE = {
    ...PENDING,
    status: "needs_license" as const,
    status_detail: "requires a valid license: no license token found",
    permissions: [],
    missing_permissions: [],
  };

  it("shows a needs_license plugin with an Add license action and activates a pasted token", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [NEEDS_LICENSE], errors: [] });
    renderPage();

    expect(await screen.findByText("License required")).toBeInTheDocument();
    expect(screen.getByText(/no license token found/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Add license/i }));
    const dialog = await screen.findByRole("dialog");
    const token = { userId: "u1", pluginId: "community.hello", signature: "ab" };
    await userEvent.click(within(dialog).getByPlaceholderText(/userId/));
    await userEvent.paste(JSON.stringify(token));
    await userEvent.click(within(dialog).getByRole("button", { name: /Activate/i }));
    await waitFor(() => expect(activateLicense).toHaveBeenCalledWith("community.hello", token));
  });

  it("rejects non-JSON license input inline without calling the API", async () => {
    diagnostics.mockResolvedValue({ loaded: [], gated: [NEEDS_LICENSE], errors: [] });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /Add license/i }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByPlaceholderText(/userId/));
    await userEvent.paste("not json");
    await userEvent.click(within(dialog).getByRole("button", { name: /Activate/i }));
    expect(await within(dialog).findByText(/invalid JSON/i)).toBeInTheDocument();
    expect(activateLicense).not.toHaveBeenCalled();
  });
});
