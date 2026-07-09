// Plugin-contributed connectors in the Connections UI: they appear as their own
// picker section with a Plugin badge, and their form is driven by the
// connector's config_schema (fields stored into options).

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ProviderInfo } from "@/lib/types";
import { ConnectionsPage } from "../ConnectionsPage";
import { useKeyringAvailability, useStoreKeyringSecret, useTestConnectionConfig } from "../hooks";

// vi.mock factories are hoisted above imports, so the fixtures they close over
// must be hoisted too.
const { CORE_PROVIDER, PLUGIN_PROVIDER, CORE_API_PROVIDER, SNOWFLAKE_PROVIDER, AZURE_PROVIDER } = vi.hoisted(() => {
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
  const snowflake: ProviderInfo = {
    ...core,
    name: "snowflake",
    label: "Snowflake",
    driver_module: "snowflake-connector-python",
    extra: "snowflake",
    default_port: null,
  };
  const azure: ProviderInfo = {
    ...core,
    name: "azure_blob",
    label: "Azure Blob Storage",
    kind: "storage",
    driver_module: "azure-storage-blob",
    extra: "azure",
    default_port: null,
    needs_host: false,
    needs_bucket: true,
    needs_endpoint: true,
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
  return {
    CORE_PROVIDER: core,
    PLUGIN_PROVIDER: plugin,
    CORE_API_PROVIDER: coreApi,
    SNOWFLAKE_PROVIDER: snowflake,
    AZURE_PROVIDER: azure,
  };
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
      data: [CORE_PROVIDER, CORE_API_PROVIDER, PLUGIN_PROVIDER, SNOWFLAKE_PROVIDER, AZURE_PROVIDER],
      refetch: vi.fn(),
      isFetching: false,
    }),
    useCreateConnection: mutationStub,
    useUpdateConnection: mutationStub,
    useDeleteConnection: mutationStub,
    useTestConnection: mutationStub,
    useTestConnectionConfig: vi.fn(mutationStub),
    useStoreKeyringSecret: vi.fn(mutationStub),
    // Default: keychain available, so the "save to keychain" affordance renders.
    useKeyringAvailability: vi.fn(() => ({
      data: { available: true, backend: null, detail: null },
    })),
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

describe("save secret to OS keychain", () => {
  afterEach(() => {
    // Restore the module-mock defaults so per-test overrides don't leak.
    vi.mocked(useKeyringAvailability).mockReturnValue({
      data: { available: true, backend: null, detail: null },
    } as any);
  });

  it("stores the value and sets the field to the keyring: reference", async () => {
    const stored: { name: string; value: string }[] = [];
    vi.mocked(useStoreKeyringSecret).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(async (body: { name: string; value: string }) => {
        stored.push(body);
        return { name: body.name, exists: true, reference: `keyring:${body.name}` };
      }),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      data: undefined,
    } as any);

    openDialog();
    fireEvent.click(screen.getByText("PostgreSQL"));

    // The affordance shows because the keychain is available (mocked).
    fireEvent.click(screen.getByText(/Store a value in the OS keychain/));
    fireEvent.change(screen.getByPlaceholderText("pg-main"), { target: { value: "pg-main" } });
    fireEvent.change(screen.getByPlaceholderText("the password / token"), {
      target: { value: "hunter2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save to keychain/i }));

    await screen.findByText(/Saved to the OS keychain/);
    expect(stored).toEqual([{ name: "pg-main", value: "hunter2", overwrite: false }]);
    // The secret input never shows the raw value as a reference — the field is
    // now keyring:pg-main.
    expect(screen.getByDisplayValue("keyring:pg-main")).toBeInTheDocument();
  });

  it("disables (does not hide) the affordance when no OS keychain is available", () => {
    vi.mocked(useKeyringAvailability).mockReturnValue({
      data: {
        available: false,
        backend: null,
        detail: "Install the OS keychain support with: pip install ciaren[keyring]",
      },
    } as any);
    openDialog();
    fireEvent.click(screen.getByText("PostgreSQL"));
    // Still shown, so the user learns the option exists…
    const btn = screen.getByText(/Store a value in the OS keychain/).closest("button");
    expect(btn).toBeInTheDocument();
    // …but disabled, and clicking it does not open the save modal.
    expect(btn).toBeDisabled();
    fireEvent.click(btn!);
    expect(screen.queryByText("Store a secret in the OS keychain")).not.toBeInTheDocument();
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
    expect(screen.getByText("Start page")).toBeInTheDocument();
    expect(screen.getByText("Verify TLS certificates")).toBeInTheDocument();
  });
});

describe("Snowflake connector", () => {
  it("collects account/warehouse/role/schema instead of the generic host+port form", () => {
    openDialog();
    fireEvent.click(screen.getByText("Snowflake"));

    // Snowflake-specific fields.
    expect(screen.getByText("Account identifier")).toBeInTheDocument();
    expect(screen.getByText("Warehouse")).toBeInTheDocument();
    expect(screen.getByText("Role")).toBeInTheDocument();
    expect(screen.getByText("Schema")).toBeInTheDocument();
    expect(screen.getByText("Username")).toBeInTheDocument();
    expect(screen.getByText("Password secret")).toBeInTheDocument();
    // No Port field — the backend's snowflake URL branch never sends one.
    expect(screen.queryByText("Port")).not.toBeInTheDocument();
  });

  it("stores warehouse/role/schema in options, and account in host", () => {
    openDialog();
    fireEvent.click(screen.getByText("Snowflake"));

    fireEvent.change(screen.getByPlaceholderText("xy12345.us-east-1"), {
      target: { value: "ab12345.us-east-1" },
    });
    fireEvent.change(screen.getByPlaceholderText("COMPUTE_WH"), { target: { value: "MY_WH" } });
    fireEvent.change(screen.getByPlaceholderText("SYSADMIN"), { target: { value: "ANALYST" } });
    fireEvent.change(screen.getByPlaceholderText("PUBLIC"), { target: { value: "RAW" } });

    expect(screen.getByPlaceholderText("xy12345.us-east-1")).toHaveValue("ab12345.us-east-1");
    expect(screen.getByPlaceholderText("COMPUTE_WH")).toHaveValue("MY_WH");
    expect(screen.getByPlaceholderText("SYSADMIN")).toHaveValue("ANALYST");
    expect(screen.getByPlaceholderText("PUBLIC")).toHaveValue("RAW");
  });
});

describe("Azure Blob Storage connector", () => {
  it("exposes an endpoint URL field for Azurite / sovereign clouds", () => {
    openDialog();
    fireEvent.click(screen.getByText("Azure Blob Storage"));

    expect(screen.getByText("Container")).toBeInTheDocument();
    expect(screen.getByText("Storage account name")).toBeInTheDocument();
    expect(screen.getByText("Account key")).toBeInTheDocument();
    const endpointInput = screen.getByPlaceholderText("http://localhost:10000/devstoreaccount1");
    expect(endpointInput).toBeInTheDocument();

    fireEvent.change(endpointInput, { target: { value: "http://localhost:10000/devstoreaccount1" } });
    expect(endpointInput).toHaveValue("http://localhost:10000/devstoreaccount1");
  });
});
