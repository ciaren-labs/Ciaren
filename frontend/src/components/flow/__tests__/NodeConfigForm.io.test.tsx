import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NodeConfigForm } from "../NodeConfigForm";
import type { Connection } from "@/features/connections/types";

function makeConnection(id: string, name: string, connection_type: string): Connection {
  return {
    id,
    name,
    provider: connection_type === "storage" ? "s3" : connection_type === "api" ? "rest" : "postgres",
    connection_type,
    host: null,
    port: null,
    database: null,
    username: null,
    password_env: null,
    options: null,
    created_at: "",
    updated_at: "",
    last_tested_at: null,
    last_test_status: null,
    last_test_error: null,
  };
}

const SQL_CONN = makeConnection("db1", "Warehouse", "sql");
const API_CONN = makeConnection("api1", "Public API", "api");
const STORAGE_CONN = makeConnection("s3-1", "Data Lake", "storage");
const MLFLOW_CONN = makeConnection("mlf1", "Local MLflow", "mlflow");

vi.mock("@/features/connections/api", () => ({
  connectionsApi: {
    list: vi.fn(() => Promise.resolve([SQL_CONN, API_CONN, STORAGE_CONN, MLFLOW_CONN])),
    tables: vi.fn(() =>
      Promise.resolve([{ name: "orders", schema_name: "public", qualified: "public.orders" }]),
    ),
    objects: vi.fn(() => Promise.resolve(["data/input.csv", "data/report.xlsx", "notes.txt", "raw.bin"])),
  },
}));

function renderForm(props: Partial<React.ComponentProps<typeof NodeConfigForm>>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <NodeConfigForm
          type="sqlInput"
          config={{}}
          datasets={[]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
          {...props}
        />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("NodeConfigForm — sqlInput connection picker", () => {
  it("excludes storage and mlflow connections from the SQL connection list", async () => {
    renderForm({ type: "sqlInput", config: {} });
    await screen.findByText("Warehouse");
    expect(screen.getByText("Public API")).toBeInTheDocument();
    expect(screen.queryByText("Data Lake")).not.toBeInTheDocument();
    expect(screen.queryByText("Local MLflow")).not.toBeInTheDocument();
  });

  it("adapts labels to 'Endpoint'/'Custom request path' for an API connection", async () => {
    renderForm({ type: "sqlInput", config: { connection_id: "api1", mode: "table" } });
    expect(await screen.findByText("Endpoint", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("Table", { selector: "label" })).not.toBeInTheDocument();
  });

  it("keeps 'Table'/'SQL query' labels for a plain SQL connection", async () => {
    renderForm({ type: "sqlInput", config: { connection_id: "db1", mode: "table" } });
    expect(await screen.findByText("Table", { selector: "label" })).toBeInTheDocument();
  });

  it("lists tables fetched from the connection once one is selected", async () => {
    renderForm({ type: "sqlInput", config: { connection_id: "db1", mode: "table" } });
    expect(await screen.findByText("public.orders")).toBeInTheDocument();
  });
});

describe("NodeConfigForm — sqlOutput connection picker", () => {
  it("excludes API connections (read-only) from the write-target list", async () => {
    renderForm({ type: "sqlOutput", config: {} });
    await screen.findByText("Warehouse");
    expect(screen.queryByText("Public API")).not.toBeInTheDocument();
  });
});

describe("NodeConfigForm — storageInput", () => {
  it("lists only supported file extensions and filters out unsupported ones", async () => {
    renderForm({ type: "storageInput", config: { connection_id: "s3-1" } });
    expect(await screen.findByText("data/input.csv")).toBeInTheDocument();
    expect(screen.getByText("data/report.xlsx")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.queryByText("raw.bin")).not.toBeInTheDocument();
  });

  it("infers the format from the picked file's extension", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderForm({ type: "storageInput", config: { connection_id: "s3-1" }, onChange });

    await user.click(await screen.findByText("data/report.xlsx"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ path: "data/report.xlsx", format: "excel" }),
    );
  });

  it("warns when the configured path is no longer present in the connection", async () => {
    renderForm({
      type: "storageInput",
      config: { connection_id: "s3-1", path: "gone/missing.csv" },
    });
    expect(await screen.findByText(/not found in connection/i)).toBeInTheDocument();
  });

  it("only shows the file picker once a connection is selected", () => {
    renderForm({ type: "storageInput", config: {} });
    expect(screen.queryByText(/Select a file from the storage connection/)).not.toBeInTheDocument();
  });
});

describe("NodeConfigForm — storageOutput", () => {
  it("defaults the 'if file exists' behavior to overwrite", () => {
    renderForm({ type: "storageOutput", config: {} });
    expect(screen.getByText("If file exists")).toBeInTheDocument();
  });

  it("renders a destination-path field with a helpful placeholder", () => {
    renderForm({ type: "storageOutput", config: {} });
    expect(screen.getByPlaceholderText("outputs/result.parquet")).toBeInTheDocument();
  });
});
