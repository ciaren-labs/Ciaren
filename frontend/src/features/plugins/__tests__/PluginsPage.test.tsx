import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const diagnostics = vi.fn();
const grant = vi.fn((_id: string, _perms: string[]) => Promise.resolve({}));
const disable = vi.fn((_id: string) => Promise.resolve({}));
const enable = vi.fn((_id: string) => Promise.resolve({}));
const revoke = vi.fn((_id: string, _perms: string[]) => Promise.resolve({}));

vi.mock("@/lib/api", () => ({
  pluginsApi: {
    diagnostics: () => diagnostics(),
    grant: (id: string, perms: string[]) => grant(id, perms),
    disable: (id: string) => disable(id),
    enable: (id: string) => enable(id),
    revoke: (id: string, perms: string[]) => revoke(id, perms),
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
};

const LOADED = { ...PENDING, status: "loaded" as const, permissions: [], missing_permissions: [] };

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
});
