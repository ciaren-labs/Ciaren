import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const diagnostics = vi.fn();
const grant = vi.fn((_id: string, _perms: string[]) => Promise.resolve({}));
const disable = vi.fn((_id: string) => Promise.resolve({}));
const enable = vi.fn((_id: string) => Promise.resolve({}));
const revoke = vi.fn((_id: string, _perms: string[]) => Promise.resolve({}));
const uninstall = vi.fn((_id: string) => Promise.resolve({ plugin_id: _id, removed: true }));
const installPlugin = vi.fn((_file: File) => Promise.resolve({ plugin: { name: "X" }, outcome: "unsigned" }));
const marketplaceList = vi.fn().mockResolvedValue({ configured: false, plugins: [] });
const marketplaceInstall = vi.fn((_id: string) => Promise.resolve({}));

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
  },
  marketplaceApi: {
    list: () => marketplaceList(),
    install: (id: string) => marketplaceInstall(id),
  },
}));

import { PluginsPage } from "../PluginsPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PluginsPage />
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
  capabilities: ["node.hello"],
  permissions: ["network"],
  granted_permissions: [],
  missing_permissions: ["network"],
  signature: "unsigned",
  nodes: ["hello.greeting"],
  node_categories: { "hello.greeting": "columns" },
  uninstallable: false,
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
  it("shows an empty state when nothing is installed", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [], errors: [] });
    renderPage();
    expect(await screen.findByText("No plugins installed")).toBeInTheDocument();
  });

  it("always shows the trust warning", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [], errors: [] });
    renderPage();
    expect(await screen.findByText(/Only install plugins you trust/i)).toBeInTheDocument();
    expect(screen.getByText(/not responsible/i)).toBeInTheDocument();
  });

  it("renders a pending plugin with its permissions and an Approve action", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [PENDING], errors: [] });
    renderPage();

    expect(await screen.findByText("Hello Plugin")).toBeInTheDocument();
    expect(screen.getByText("Needs approval")).toBeInTheDocument();
    // The requested permission is shown with its friendly description.
    expect(screen.getByText("network")).toBeInTheDocument();
    expect(screen.getByText(/Make network requests/)).toBeInTheDocument();
    expect(screen.getByText("hello.greeting")).toBeInTheDocument();
    expect(screen.getByText("Columns")).toBeInTheDocument();
    expect(screen.getByText(/not loaded/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => expect(grant).toHaveBeenCalledWith("community.hello", []));
  });

  it("renders a loaded plugin with a Disable action", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    expect(await screen.findByText("Active")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Disable/i }));
    await waitFor(() => expect(disable).toHaveBeenCalledWith("community.hello"));
  });

  it("shows a loaded plugin's permissions as active, not 'not granted'", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED_APPROVED], gated: [], errors: [] });
    renderPage();

    expect(await screen.findByText("Active")).toBeInTheDocument();
    // The permission is listed…
    expect(screen.getByText("network")).toBeInTheDocument();
    // …but never flagged as "(not granted)" for a plugin that is already running.
    expect(screen.queryByText(/not granted/i)).not.toBeInTheDocument();
  });

  it("revokes a previously-approved plugin's permissions", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED_APPROVED], gated: [], errors: [] });
    renderPage();

    await screen.findByText("Hello Plugin");
    await userEvent.click(screen.getByRole("button", { name: /Revoke/i }));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("community.hello", ["network"]));
  });

  it("does not offer Revoke for a plugin with no granted permissions", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    await screen.findByText("Active");
    expect(screen.queryByRole("button", { name: /Revoke/i })).not.toBeInTheDocument();
  });

  it("uninstalls a managed plugin after confirmation", async () => {
    diagnostics.mockResolvedValueOnce({
      loaded: [{ ...LOADED, uninstallable: true }],
      gated: [],
      errors: [],
    });
    renderPage();

    await screen.findByText("Hello Plugin");
    await userEvent.click(screen.getByRole("button", { name: /Uninstall/i }));
    // A destructive confirm dialog gates the delete; nothing happens until confirmed.
    expect(uninstall).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /Uninstall/i }));
    await waitFor(() => expect(uninstall).toHaveBeenCalledWith("community.hello"));
  });

  it("does not offer Uninstall for a dev-dir / entry-point plugin", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED], gated: [], errors: [] });
    renderPage();

    await screen.findByText("Active");
    expect(screen.queryByRole("button", { name: /Uninstall/i })).not.toBeInTheDocument();
  });

  it("shows the install-time signature trust badge", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [LOADED], gated: [PENDING], errors: [] });
    renderPage();

    // LOADED verified as trusted; PENDING was an unsigned drop-in.
    expect(await screen.findByText("Trusted")).toBeInTheDocument();
    expect(screen.getByText("Unsigned")).toBeInTheDocument();
  });

  it("surfaces load errors", async () => {
    diagnostics.mockResolvedValueOnce({
      loaded: [],
      gated: [],
      errors: [{ source: "dir:broken", error: "bad manifest" }],
    });
    renderPage();
    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByText("dir:broken")).toBeInTheDocument();
  });

  it("uploads a selected .ciarenplugin file via the Install button", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [], errors: [] });
    renderPage();

    await screen.findByText("No plugins installed");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3])], "acme.ciarenplugin");
    await userEvent.upload(input, file);
    await waitFor(() => expect(installPlugin).toHaveBeenCalledTimes(1));
    expect(installPlugin.mock.calls[0][0].name).toBe("acme.ciarenplugin");
  });

  it("shows a configured catalog and installs an entry", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValueOnce({
      configured: true,
      plugins: [
        {
          id: "acme.databricks",
          name: "Databricks Connector",
          version: "1.0.0",
          publisher: "acme",
          description: "Connect to Databricks.",
          license: "commercial",
          trust: "verified",
          capabilities: ["connector.databricks"],
          permissions: ["network", "credentials"],
          nodes: ["databricks.query"],
          node_categories: { "databricks.query": "input" },
          license_required: true,
          installed: false,
          installable: true,
        },
      ],
    });
    renderPage();

    expect(await screen.findByText("Databricks Connector")).toBeInTheDocument();
    expect(screen.getByText("databricks.query")).toBeInTheDocument();
    expect(screen.getByText("Inputs")).toBeInTheDocument();
    expect(screen.getByText("License required")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Install$/i }));
    await waitFor(() => expect(marketplaceInstall).toHaveBeenCalledWith("acme.databricks"));
  });

  it("marks an already-installed catalog entry as Installed", async () => {
    diagnostics.mockResolvedValueOnce({ loaded: [], gated: [], errors: [] });
    marketplaceList.mockResolvedValueOnce({
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
          nodes: ["acme.xNode"],
          node_categories: { "acme.xNode": "plugins" },
          license_required: false,
          installed: true,
          installable: true,
        },
      ],
    });
    renderPage();

    expect(await screen.findByText("Installed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Install$/i })).not.toBeInTheDocument();
  });
});
