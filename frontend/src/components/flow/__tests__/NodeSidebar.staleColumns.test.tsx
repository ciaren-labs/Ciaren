// AUDIT REPRO — demonstrates a correctness bug in NodeSidebar.handleConfigChange:
// when an input node's dataset changes, downstream column refs are validated
// against the *raw dataset schema* instead of each node's own propagated input
// columns (computeNodeColumns). Columns created mid-pipeline (calculatedColumn,
// renameColumns, binColumn, …) and columns arriving from the *other* branch of
// a fan-in (join) are therefore wrongly treated as stale and wiped.
//
// The `it` blocks assert the CORRECT behaviour, so they FAIL against the
// current code. They are marked `.fails` so the suite stays green while the
// bug exists — remove `.fails` after fixing NodeSidebar to see them pass.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NodeSidebar } from "../NodeSidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

const ds = (id: string, name: string, cols: string[]) => ({
  id,
  name,
  source_type: "csv",
  dataset_kind: "input",
  is_disabled: false,
  project_id: "p1",
  latest_version: 1,
  version_count: 1,
  column_schema: cols.map((c) => ({ name: c, type: "string" })),
  data_sample: null,
  column_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});

const DATASETS = [
  ds("ds1", "Sales", ["a", "b"]),
  ds("ds2", "Sales v2", ["a", "b"]), // identical schema to ds1!
  ds("dsB", "Lookup", ["k", "v"]),
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => ({
      ok: true,
      status: 200,
      json: async () => (String(url).includes("/datasets") ? DATASETS : []),
    })),
  );
  useFlowEditorStore.getState().reset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  useFlowEditorStore.getState().reset();
});

function renderSidebar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <NodeSidebar />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

/** The <select> under the "Dataset" field (the one listing dataset names). */
async function datasetSelect(): Promise<HTMLSelectElement> {
  return await waitFor(() => {
    const all = screen.getAllByRole("combobox") as HTMLSelectElement[];
    const sel = all.find((s) =>
      Array.from(s.options).some((o) => o.textContent === "Sales v2"),
    );
    if (!sel) throw new Error("dataset select not ready");
    return sel;
  });
}

const node = (id: string, type: string, config: Record<string, unknown>) => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data: { label: type, config },
});

describe("NodeSidebar dataset-change stale-column cleanup (BUG repro)", () => {
  it(
    "keeps a downstream ref to a column created by calculatedColumn",
    async () => {
      useFlowEditorStore.setState({
        selectedNodeId: "n1",
        flowProjectId: "p1",
        nodes: [
          node("n1", "fileInput", { dataset_id: "ds1", dataset_version: 1, format: "csv" }),
          node("n2", "calculatedColumn", { column_name: "profit", expression: "a * 2" }),
          node("n3", "filterRows", { column: "profit", operator: ">", value: "0" }),
        ],
        edges: [
          { id: "e1", source: "n1", target: "n2" },
          { id: "e2", source: "n2", target: "n3" },
        ],
        parameters: [],
      });

      renderSidebar();
      // Switch the input to ds2 — which has the *same* columns as ds1.
      fireEvent.change(await datasetSelect(), { target: { value: "ds2" } });

      const n3 = useFlowEditorStore.getState().nodes.find((n) => n.id === "n3")!;
      // "profit" is produced by n2 regardless of the dataset, so the filter's
      // column ref is still valid — but the cleanup wipes it to "" because it
      // only checks the new dataset's schema {a, b}.
      expect(n3.data.config.column).toBe("profit");
    },
  );

  it(
    "does not wipe a join's right-side keys when the LEFT input's dataset changes",
    async () => {
      useFlowEditorStore.setState({
        selectedNodeId: "n1",
        flowProjectId: "p1",
        nodes: [
          node("n1", "fileInput", { dataset_id: "ds1", dataset_version: 1, format: "csv" }),
          node("nB", "fileInput", { dataset_id: "dsB", dataset_version: 1, format: "csv" }),
          node("nJ", "join", { how: "inner", on: [], left_on: ["a"], right_on: ["k"] }),
        ],
        edges: [
          { id: "e1", source: "n1", target: "nJ", targetHandle: "left" },
          { id: "e2", source: "nB", target: "nJ", targetHandle: "right" },
        ],
        parameters: [],
      });

      renderSidebar();
      fireEvent.change(await datasetSelect(), { target: { value: "ds2" } });

      const nJ = useFlowEditorStore.getState().nodes.find((n) => n.id === "nJ")!;
      // "k" comes from the OTHER (right) input, which did not change — but the
      // cleanup validates it against the left input's new schema {a, b} and
      // clears it, silently breaking the join config.
      expect(nJ.data.config.right_on).toEqual(["k"]);
    },
  );
});
