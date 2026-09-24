import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NodeConfigForm } from "../NodeConfigForm";
import type { Connection } from "@/features/connections/types";
import { connectionsApi } from "@/features/connections/api";

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
    objectDialect: vi.fn(() => Promise.resolve({ delimiter: null, encoding: null, decimal: null })),
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

describe("NodeConfigForm — storageInput CSV dialect", () => {
  const CSV_CONFIG = { connection_id: "s3-1", path: "data/input.csv", format: "csv" };

  it("shows the detected dialect and pre-fills the override fields from it", async () => {
    vi.mocked(connectionsApi.objectDialect).mockResolvedValueOnce({
      delimiter: ";",
      encoding: "cp1252",
      decimal: ",",
    });
    const onChange = vi.fn();
    renderForm({ type: "storageInput", config: CSV_CONFIG, onChange });

    expect(await screen.findByText("Detected: Semicolon (;) · cp1252 · decimal comma")).toBeInTheDocument();
    expect(connectionsApi.objectDialect).toHaveBeenCalledWith("s3-1", "data/input.csv", "csv");
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({ ...CSV_CONFIG, delimiter: ";", encoding: "cp1252", decimal: "," }),
    );
  });

  it("keeps explicit overrides over detection, and the user can still change them", async () => {
    const user = userEvent.setup();
    vi.mocked(connectionsApi.objectDialect).mockResolvedValueOnce({ delimiter: ";", encoding: "cp1252", decimal: null });
    const onChange = vi.fn();
    renderForm({ type: "storageInput", config: { ...CSV_CONFIG, delimiter: "|" }, onChange });

    await screen.findByText("Detected: Semicolon (;) · cp1252");
    expect(onChange).not.toHaveBeenCalled(); // no pre-fill over an explicit value

    await user.selectOptions(screen.getByLabelText("Encoding"), "latin-1");
    expect(onChange).toHaveBeenLastCalledWith({ ...CSV_CONFIG, delimiter: "|", encoding: "latin-1" });
  });

  it.each([
    ["nothing detected", () => Promise.resolve({ delimiter: null, encoding: null, decimal: null }), /No dialect detected/],
    ["detection failed", () => Promise.reject(new Error("File not found")), /Couldn't detect the dialect/],
  ])("shows no 'Detected' value and pre-fills nothing when %s", async (_label, result, message) => {
    vi.mocked(connectionsApi.objectDialect).mockImplementationOnce(result);
    const onChange = vi.fn();
    renderForm({ type: "storageInput", config: CSV_CONFIG, onChange });

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText(/^Detected:/)).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("clears overrides when another file is picked, and hides dialect fields for non-delimited formats", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { unmount } = renderForm({ type: "storageInput", config: { ...CSV_CONFIG, delimiter: ";" }, onChange });

    await user.click(await screen.findByText("data/report.xlsx"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ path: "data/report.xlsx", format: "excel", delimiter: undefined }),
    );
    expect(screen.getByLabelText("Decimal mark")).toBeInTheDocument();

    unmount();
    renderForm({ type: "storageInput", config: { connection_id: "s3-1", path: "data/report.xlsx", format: "excel" } });
    await screen.findByText("data/report.xlsx");
    expect(screen.queryByLabelText("Decimal mark")).not.toBeInTheDocument();
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
