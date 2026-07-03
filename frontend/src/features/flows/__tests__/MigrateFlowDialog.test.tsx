import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MigrateFlowDialog } from "../MigrateFlowDialog";

let fetchMock: ReturnType<typeof vi.fn>;

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MigrateFlowDialog open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

// jsdom's File shim in this test environment doesn't implement `.text()`
// (used by the real onFile handler, mirroring FlowListPage's import flow) —
// patch it in so these tests exercise the same code path as the browser.
function fileWithText(content: string, name: string, type: string): File {
  const file = new File([content], name, { type });
  Object.defineProperty(file, "text", { value: () => Promise.resolve(content) });
  return file;
}

function selectFile(json: unknown, name = "old.flow.json") {
  const file = fileWithText(JSON.stringify(json), name, "application/json");
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MigrateFlowDialog", () => {
  it("reports an already-current document without a download action", async () => {
    fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        document: { schemaVersion: "1.0.0", project: { name: "x" }, graph: { nodes: [], edges: [] } },
        migrated: false,
        from_version: "1.0.0",
        to_version: "1.0.0",
      }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    renderDialog();
    selectFile({ format: "ciaren.flow/v1", name: "x", graph_json: { nodes: [], edges: [] } });

    expect(await screen.findByText(/already up to date/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/flows/migrate-document");
    expect(screen.queryByRole("button", { name: /download migrated file/i })).not.toBeInTheDocument();
  });

  it("offers a download once an older document is migrated", async () => {
    fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        document: { schemaVersion: "1.0.0", project: { name: "old" }, graph: { nodes: [], edges: [] } },
        migrated: true,
        from_version: "0.9.0",
        to_version: "1.0.0",
      }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    renderDialog();
    selectFile({ schemaVersion: "0.9.0", project: { name: "old" }, graph: { nodes: [], edges: [] } });

    expect(await screen.findByText(/upgraded from schema v0\.9\.0 to v1\.0\.0/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download migrated file/i })).toBeInTheDocument();
  });

  it("shows a parse error inline for invalid JSON and never calls the API", async () => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderDialog();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = fileWithText("not json", "bad.json", "application/json");
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/isn't valid json/i)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
