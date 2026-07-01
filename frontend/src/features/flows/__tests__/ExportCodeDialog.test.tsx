import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ExportCodeDialog } from "../ExportCodeDialog";

// Three distinct scripts so each tab is identifiable by a unique substring.
const EXPORT_RESPONSE = {
  code: 'import pandas as pd\ndf_1 = pd.read_csv("sales.csv")\n',
  polars: 'import polars as pl\ndf_1 = pl.read_csv("sales.csv")\n',
  polars_lazy: 'import polars as pl\ndf_1 = pl.scan_csv("sales.csv")\n',
  flow_document: {
    format: "ciaren.flow/v1",
    name: "Sales",
    description: null,
    graph_json: { nodes: [], edges: [] },
  },
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  // Mock fetch (not the api module) so the real api -> hook -> dialog wiring,
  // including the free_intermediates query param, is exercised end to end.
  fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => EXPORT_RESPONSE,
  }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ExportCodeDialog flowId="f1" open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("ExportCodeDialog", () => {
  it("offers pandas, polars and lazy-polars tabs", async () => {
    renderDialog();
    await screen.findByText(/pd\.read_csv/, { selector: "code" });

    expect(screen.getByRole("tab", { name: "pandas" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "polars" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "polars (lazy)" })).toBeInTheDocument();
  });

  it("reveals the lazy scan_csv script on the lazy tab", async () => {
    const user = userEvent.setup();
    renderDialog();
    await screen.findByText(/pd\.read_csv/, { selector: "code" });

    // Radix Tabs activate on focus, so use userEvent (full pointer+focus
    // sequence) rather than a bare fireEvent.click.
    await user.click(screen.getByRole("tab", { name: "polars (lazy)" }));

    expect(
      await screen.findByText(/scan_csv/, { selector: "code" }),
    ).toBeInTheDocument();
  });

  it("shows the importable Flow JSON document on its tab", async () => {
    const user = userEvent.setup();
    renderDialog();
    await screen.findByText(/pd\.read_csv/, { selector: "code" });

    await user.click(screen.getByRole("tab", { name: "Flow JSON" }));

    expect(await screen.findByText(/ciaren\.flow\/v1/, { selector: "code" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument();
  });

  it("does not crash when the response has no flow_document (older backend)", async () => {
    // Regression: the JSON tab read flow_document.name eagerly, blanking the page
    // when an older backend omitted the field. The tab should simply be absent.
    fetchMock.mockImplementation(async () => ({
      ok: true,
      status: 200,
      json: async () => {
        const { flow_document: _omit, ...rest } = EXPORT_RESPONSE;
        return rest;
      },
    }));
    renderDialog();
    await screen.findByText(/pd\.read_csv/, { selector: "code" });
    expect(screen.getByRole("tab", { name: "pandas" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Flow JSON" })).not.toBeInTheDocument();
  });

  it("re-exports with free_intermediates when the del option is checked", async () => {
    renderDialog();
    await screen.findByText(/pd\.read_csv/, { selector: "code" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/flows/f1/export/python");

    fireEvent.click(
      screen.getByRole("checkbox", { name: /free intermediate tables/i }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/flows/f1/export/python?free_intermediates=true",
    );
  });
});
