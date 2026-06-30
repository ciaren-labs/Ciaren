import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NodeSidebar } from "../NodeSidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => [] })),
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

describe("NodeSidebar parameter affordance", () => {
  it("lists declared parameters and flags unknown references", () => {
    useFlowEditorStore.setState({
      selectedNodeId: "n1",
      nodes: [
        {
          id: "n1",
          type: "csvOutput",
          position: { x: 0, y: 0 },
          data: { label: "Out", config: { dataset_name: "{{ out }}", extra: "{{ missing }}" } },
        },
      ],
      edges: [],
      parameters: [{ name: "out", type: "string", default: "result.csv" }],
    });

    renderSidebar();

    // Declared parameter shown as an insertable chip.
    expect(screen.getByText("{{ out }}")).toBeInTheDocument();
    // Unknown reference is surfaced as a warning.
    expect(screen.getByText(/unknown parameter/i)).toBeInTheDocument();
    expect(screen.getByText(/missing/)).toBeInTheDocument();
  });

  it("shows no parameter hint when the flow declares none", () => {
    useFlowEditorStore.setState({
      selectedNodeId: "n1",
      nodes: [
        {
          id: "n1",
          type: "csvOutput",
          position: { x: 0, y: 0 },
          data: { label: "Out", config: { dataset_name: "clean" } },
        },
      ],
      edges: [],
      parameters: [],
    });

    renderSidebar();
    expect(screen.queryByText(/Flow parameters/)).not.toBeInTheDocument();
    expect(screen.queryByText(/unknown parameter/i)).not.toBeInTheDocument();
  });

  it("loads datasets scoped to the active flow project", async () => {
    useFlowEditorStore.setState({
      selectedNodeId: "n1",
      flowProjectId: "p1",
      nodes: [
        {
          id: "n1",
          type: "fileInput",
          position: { x: 0, y: 0 },
          data: { label: "Input", config: { dataset_id: "", format: "csv" } },
        },
      ],
      edges: [],
      parameters: [],
    });

    renderSidebar();

    await waitFor(() => {
      const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map(([url]) => String(url));
      expect(calls).toContain("/api/datasets?project_id=p1");
    });
  });
});
