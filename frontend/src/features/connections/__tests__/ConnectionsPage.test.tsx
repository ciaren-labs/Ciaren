// Plugin-contributed connectors in the Connections UI: they appear as their own
// picker section with a Plugin badge, and their form is driven by the
// connector's config_schema (fields stored into options).

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ProviderInfo } from "@/lib/types";
import { ConnectionsPage } from "../ConnectionsPage";
import { useTestConnectionConfig } from "../hooks";

// vi.mock factories are hoisted above imports, so the fixtures they close over
// must be hoisted too.
const { CORE_PROVIDER, PLUGIN_PROVIDER, CORE_API_PROVIDER } = vi.hoisted(() => {
  const core: ProviderInfo = {
    name: "postgresql",
    label: "PostgreSQL",
    kind: "sql",
    available: true,
    driver_module: "psycopg",
    extra: "postgres",
    default_port: 5432,
    needs_host: true,
    needs_auth: true,
    supports_query: true,
    needs_bucket: false,
    needs_region: false,
    needs_endpoint: false,
  };
  const plugin: ProviderInfo = {
    ...core,
    name: "rest-api",
    label: "REST API",
    kind: "api",
    driver_module: null,
    extra: null,
    default_port: null,
    needs_host: false,
    needs_auth: true,
    supports_query: false,
    plugin: true,
    plugin_id: "community.rest-connector",
    config_schema: {
      fields: [
        { key: "base_url", label: "Base URL", type: "string", required: true },
        { key: "verify_tls", type: "boolean", default: true },
      ],
    },
  };
  const coreApi: ProviderInfo = {
    ...core,
    name: "rest_api",
    label: "REST API (core)",
    kind: "api",
    driver_module: null,
    extra: null,
    default_port: null,
    needs_host: true,
    needs_auth: true,
    supports_query: true,
  };
  return { CORE_PROVIDER: core, PLUGIN_PROVIDER: plugin, CORE_API_PROVIDER: coreApi };
});

vi.mock("../hooks", () => {
  const mutationStub = () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
  });
  return {
    useConnections: () => ({
      data: [],
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    }),
    useConnectionProviders: () => ({
      data: [CORE_PROVIDER, CORE_API_PROVIDER, PLUGIN_PROVIDER],
      refetch: vi.fn(),
      isFetching: false,
    }),
    useCreateConnection: mutationStub,
    useUpdateConnection: mutationStub,
    useDeleteConnection: mutationStub,
    useTestConnection: mutationStub,
    useTestConnectionConfig: vi.fn(mutationStub),
  };
});

function openDialog() {
  render(
    <TooltipProvider>
      <ConnectionsPage />
    </TooltipProvider>,
  );
  // Header + empty-state both offer the button; either opens the same dialog.
  fireEvent.click(screen.getAllByRole("button", { name: /add connection/i })[0]);
}

describe("ConnectionsPage plugin connectors", () => {
  it("lists plugin connectors in their own picker section with a badge", () => {
    openDialog();
    expect(screen.getByText("From plugins")).toBeInTheDocument();
    expect(screen.getByText("REST API")).toBeInTheDocument();
    expect(screen.getByText("Plugin")).toBeInTheDocument();
    expect(screen.getByText(/community\.rest-connector/)).toBeInTheDocument();
    // The core section does not absorb the plugin provider.
    expect(screen.getByText("Databases")).toBeInTheDocument();
  });

  it("renders the schema-driven form after picking a plugin connector", () => {
    openDialog();
    fireEvent.click(screen.getByText("REST API"));

    // Standard flag-driven fields: needs_auth → username + password secret ref.
    expect(screen.getByText("Username")).toBeInTheDocument();
    expect(screen.getByText("Password secret")).toBeInTheDocument();
    // Schema fields from config_schema.
    expect(screen.getByText("Base URL *")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeChecked(); // verify_tls default
    // No host fields (needs_host false).
    expect(screen.queryByText("Host")).not.toBeInTheDocument();
  });
});

describe("Test connection failure feedback", () => {
  it("surfaces the backend's error message as visible text, not just a red button", () => {
    // Simulates the 422 from POST /api/connections/test-config (e.g. a bad
    // SQLite file path) — the mutation's `error` carries the real backend
    // message, which the button must render, not just discard.
    vi.mocked(useTestConnectionConfig).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: true,
      error: { message: "unable to open database file: /bad/path.db" },
      data: undefined,
    } as any);

    openDialog();
    fireEvent.click(screen.getByText("PostgreSQL"));

    // The button itself reflects failure ("Failed"), and the real message is
    // now also rendered as visible text near it, not just a title attribute.
    expect(screen.getByRole("button", { name: /failed/i })).toBeInTheDocument();
    expect(
      screen.getByText("unable to open database file: /bad/path.db"),
    ).toBeInTheDocument();
  });
});

describe("core REST API connector", () => {
  it("shows the APIs picker section and the commercial-style form", () => {
    openDialog();
    expect(screen.getByText("APIs")).toBeInTheDocument();
    fireEvent.click(screen.getByText("REST API (core)"));

    // Primary fields.
    expect(screen.getByText("Base URL")).toBeInTheDocument();
    expect(screen.getByText("Authentication")).toBeInTheDocument();
    expect(screen.getByText("Endpoints")).toBeInTheDocument();
    // No auth by default → no secret field until an auth method is picked.
    expect(screen.queryByText("Secret", { selector: "label" })).not.toBeInTheDocument();

    // Picking API-key auth reveals the header + secret reference fields.
    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "api_key" } });
    expect(screen.getByText("API key header", { selector: "label" })).toBeInTheDocument();
    expect(screen.getByText("Secret", { selector: "label" })).toBeInTheDocument();

    // Advanced options are collapsed behind a toggle.
    fireEvent.click(screen.getByText(/Advanced options/));
    expect(screen.getByText("Custom headers")).toBeInTheDocument();
    expect(screen.getByText("Records path")).toBeInTheDocument();
    expect(screen.getByText("Page param")).toBeInTheDocument();
    expect(screen.getByText("Verify TLS certificates")).toBeInTheDocument();
  });
});
