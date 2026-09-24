import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import { FlowCanvas } from "../FlowCanvas";
import { NODE_DND_MIME } from "../NodePalette";
import { TooltipProvider } from "@/components/ui/tooltip";
import { readRecentNodeTypes } from "@/features/flows/recentNodes";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

beforeEach(() => {
  // React Flow measures its viewport; jsdom has no ResizeObserver.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  useFlowEditorStore.getState().reset();
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  useFlowEditorStore.getState().reset();
  localStorage.clear();
});

function dropPaletteNode(type: string) {
  const { container } = render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
  fireEvent.drop(container.querySelector(".react-flow")!, {
    dataTransfer: { getData: (key: string) => (key === NODE_DND_MIME ? type : "") },
  });
}

describe("FlowCanvas palette drop", () => {
  it.each([
    { name: "records a node the drop places", type: "fileInput", placed: 1, recent: ["fileInput"] },
    // Without a ready input the canvas rejects non-start nodes; nothing is recorded.
    { name: "does not record a rejected drop", type: "sortRows", placed: 0, recent: [] },
  ])("$name", ({ type, placed, recent }) => {
    dropPaletteNode(type);

    expect(useFlowEditorStore.getState().nodes).toHaveLength(placed);
    expect(readRecentNodeTypes()).toEqual(recent);
  });
});
