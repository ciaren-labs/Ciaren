import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { FlowNode } from "../FlowNode";
import { useFlowEditorStore, type FlowNodeType } from "@/stores/flowEditorStore";
import { useToastStore } from "@/stores/toastStore";

function node(id: string): FlowNodeType {
  return {
    id,
    type: "dropNulls",
    position: { x: 10, y: 20 },
    data: { label: id, config: {} },
  };
}

const testQueryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderNode(id: string, selected = false) {
  useFlowEditorStore.getState().reset();
  useFlowEditorStore.getState().setGraph([node(id)], []);
  const props = { id, type: "dropNulls", data: { label: id, config: {} }, selected } as unknown as NodeProps<FlowNodeType>;
  return render(
    <QueryClientProvider client={testQueryClient}>
      <ReactFlowProvider>
        <FlowNode {...props} />
      </ReactFlowProvider>
    </QueryClientProvider>,
  );
}

describe("FlowNode hover toolbar", () => {
  it("selects the node when Edit is clicked", async () => {
    const user = userEvent.setup();
    renderNode("a");

    await user.click(screen.getByRole("button", { name: "Edit node" }));

    expect(useFlowEditorStore.getState().selectedNodeId).toBe("a");
    expect(useFlowEditorStore.getState().sidebarOpen).toBe(true);
  });

  it("duplicates the node when Duplicate is clicked", async () => {
    const user = userEvent.setup();
    renderNode("a");

    await user.click(screen.getByRole("button", { name: "Duplicate node" }));

    const { nodes } = useFlowEditorStore.getState();
    expect(nodes).toHaveLength(2);
    expect(nodes.some((n) => n.id !== "a")).toBe(true);
  });

  it("removes the node when Delete is clicked", async () => {
    const user = userEvent.setup();
    renderNode("a");

    await user.click(screen.getByRole("button", { name: "Delete node" }));

    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);
  });

  it("shows an undoable toast when Delete is clicked", async () => {
    const user = userEvent.setup();
    useToastStore.setState({ toasts: [] });
    renderNode("a");

    await user.click(screen.getByRole("button", { name: "Delete node" }));

    const [t] = useToastStore.getState().toasts;
    expect(t).toMatchObject({ variant: "success", title: "Node deleted" });
    expect(t.action?.label).toBe("Undo");

    t.action?.onClick?.();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].id).toBe("a");
  });

  it("shows no toast if the node was already removed by the time Delete/Duplicate is clicked", async () => {
    // A stale toolbar button (e.g. the node was removed by an undo/redo or a
    // different action in the same tick) shouldn't produce a misleading
    // "success" toast with an Undo button that doesn't correspond to anything.
    const user = userEvent.setup();
    useToastStore.setState({ toasts: [] });
    renderNode("a");
    useFlowEditorStore.getState().removeNode("a");

    await user.click(screen.getByRole("button", { name: "Delete node" }));
    await user.click(screen.getByRole("button", { name: "Duplicate node" }));

    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("shows an undoable toast when Duplicate is clicked", async () => {
    const user = userEvent.setup();
    useToastStore.setState({ toasts: [] });
    renderNode("a");

    await user.click(screen.getByRole("button", { name: "Duplicate node" }));

    const [t] = useToastStore.getState().toasts;
    expect(t).toMatchObject({ variant: "success", title: "Node duplicated" });

    t.action?.onClick?.();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
  });

  it("shows the toolbar without requiring hover in jsdom (visibility is CSS-only)", () => {
    // jsdom doesn't evaluate the `group-hover` CSS that hides the toolbar until
    // hover, so the buttons are always present in the DOM — only their opacity
    // changes at runtime. This asserts the buttons render regardless of the
    // `selected` prop, which is the other trigger for full opacity.
    renderNode("a", false);
    expect(screen.getByRole("button", { name: "Edit node" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Duplicate node" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete node" })).toBeInTheDocument();
  });

  it("clicking a toolbar button does not bubble to an ancestor onClick", async () => {
    // FlowCanvas relies on onNodeClick — a React onClick registered by React
    // Flow on an ancestor of this component's rendered tree — to select or
    // deselect nodes. The toolbar buttons must call stopPropagation so a
    // click on them doesn't also fire that outer (React, not native) handler.
    // The wrapping onClick below stands in for React Flow's own delegated
    // handler, since both are ordinary React synthetic events at this layer.
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph([node("a")], []);
    const props = { id: "a", type: "dropNulls", data: { label: "a", config: {} }, selected: false } as unknown as NodeProps<FlowNodeType>;
    let bubbled = false;
    render(
      <QueryClientProvider client={testQueryClient}>
        <ReactFlowProvider>
          <div onClick={() => { bubbled = true; }}>
            <FlowNode {...props} />
          </div>
        </ReactFlowProvider>
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Duplicate node" }));

    expect(bubbled).toBe(false);
  });
});
