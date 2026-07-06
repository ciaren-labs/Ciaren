import { beforeEach, describe, expect, it } from "vitest";
import type { NodeChange } from "@xyflow/react";
import { useFlowEditorStore, type FlowNodeType } from "../flowEditorStore";

function node(id: string, config: Record<string, unknown> = {}): FlowNodeType {
  return {
    id,
    type: "dropNulls",
    position: { x: 0, y: 0 },
    data: { label: id, config },
  };
}

beforeEach(() => {
  useFlowEditorStore.getState().reset();
});

describe("flowEditorStore undo/redo", () => {
  it("undoes and redoes addNode", () => {
    const { addNode, undo, redo } = useFlowEditorStore.getState();
    addNode(node("a"));
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);

    undo();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);
    expect(useFlowEditorStore.getState().future).toHaveLength(1);

    redo();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().future).toHaveLength(0);
  });

  it("undo/redo are no-ops on empty stacks", () => {
    const { undo, redo } = useFlowEditorStore.getState();
    undo();
    redo();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);
  });

  it("removeNode is undoable and restores edges to that node", () => {
    const { setGraph, removeNode, undo } = useFlowEditorStore.getState();
    setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );
    removeNode("a");
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().edges).toHaveLength(0);

    undo();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(2);
    expect(useFlowEditorStore.getState().edges).toHaveLength(1);
  });

  it("coalesces rapid config edits to the same node into one undo step", () => {
    const { setGraph, updateNodeConfig, undo } = useFlowEditorStore.getState();
    setGraph([node("a", { value: "" })], []);

    updateNodeConfig("a", { value: "h" });
    updateNodeConfig("a", { value: "he" });
    updateNodeConfig("a", { value: "hel" });
    updateNodeConfig("a", { value: "hello" });

    expect(useFlowEditorStore.getState().past).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].data.config.value).toBe("hello");

    undo();
    expect(useFlowEditorStore.getState().nodes[0].data.config.value).toBe("");
  });

  it("does not coalesce edits to different nodes", () => {
    const { setGraph, updateNodeConfig } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], []);

    updateNodeConfig("a", { value: "1" });
    updateNodeConfig("b", { value: "2" });

    expect(useFlowEditorStore.getState().past).toHaveLength(2);
  });

  it("coalesces a node drag (position changes) into one undo step", () => {
    const { setGraph, onNodesChange, undo } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    const drag = (x: number, dragging: boolean): NodeChange<FlowNodeType>[] => [
      { id: "a", type: "position", position: { x, y: 0 }, dragging },
    ];
    onNodesChange(drag(10, true));
    onNodesChange(drag(20, true));
    onNodesChange(drag(30, false));

    expect(useFlowEditorStore.getState().past).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].position.x).toBe(30);

    undo();
    expect(useFlowEditorStore.getState().nodes[0].position.x).toBe(0);
  });

  it("does not push history for selection-only changes", () => {
    const { setGraph, onNodesChange } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    onNodesChange([{ id: "a", type: "select", selected: true }]);

    expect(useFlowEditorStore.getState().past).toHaveLength(0);
  });

  it("clears history on setGraph and reset", () => {
    const { addNode, setGraph, reset } = useFlowEditorStore.getState();
    addNode(node("a"));
    expect(useFlowEditorStore.getState().past.length).toBeGreaterThan(0);

    setGraph([], []);
    expect(useFlowEditorStore.getState().past).toHaveLength(0);

    addNode(node("b"));
    reset();
    expect(useFlowEditorStore.getState().past).toHaveLength(0);
    expect(useFlowEditorStore.getState().future).toHaveLength(0);
  });

  it("a new undo-able edit clears the redo stack", () => {
    const { addNode, undo } = useFlowEditorStore.getState();
    addNode(node("a"));
    addNode(node("b"));
    undo();
    expect(useFlowEditorStore.getState().future).toHaveLength(1);

    addNode(node("c"));
    expect(useFlowEditorStore.getState().future).toHaveLength(0);
  });
});

describe("flowEditorStore dirty state", () => {
  it("stays clean after loading a flow and running the untracked initial auto-layout", () => {
    // Mirrors FlowCanvas's one-time initial-layout effect: setGraph loads the
    // saved flow (clean), then setNodes re-positions nodes for display only.
    // Re-laying out on load isn't a user edit, so it must not flip `dirty` —
    // otherwise every freshly opened flow would show "unsaved" immediately.
    const { setGraph, setNodes } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], []);
    expect(useFlowEditorStore.getState().dirty).toBe(false);

    setNodes([
      { ...useFlowEditorStore.getState().nodes[0], position: { x: 123.456, y: 78.9 } },
      { ...useFlowEditorStore.getState().nodes[1], position: { x: 200, y: 78.9 } },
    ]);

    expect(useFlowEditorStore.getState().dirty).toBe(false);
  });

  it("still marks dirty for a user-triggered re-layout (Auto-arrange button)", () => {
    const { setGraph, relayoutNodes } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], []);
    expect(useFlowEditorStore.getState().dirty).toBe(false);

    relayoutNodes([
      { ...useFlowEditorStore.getState().nodes[0], position: { x: 1, y: 1 } },
      { ...useFlowEditorStore.getState().nodes[1], position: { x: 2, y: 2 } },
    ]);

    expect(useFlowEditorStore.getState().dirty).toBe(true);
  });

  it("stays clean when React Flow's ResizeObserver reports node dimensions after load", () => {
    // React Flow fires onNodesChange with type "dimensions" for every node the
    // first time it's measured after mounting — this happens on every flow
    // load, with zero user interaction, and must not flip `dirty`.
    const { setGraph, onNodesChange } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], []);
    expect(useFlowEditorStore.getState().dirty).toBe(false);

    const dimensionChanges: NodeChange<FlowNodeType>[] = [
      { id: "a", type: "dimensions", dimensions: { width: 220, height: 64 } },
      { id: "b", type: "dimensions", dimensions: { width: 220, height: 64 } },
    ];
    onNodesChange(dimensionChanges);

    expect(useFlowEditorStore.getState().dirty).toBe(false);
  });

  it("marks dirty for a real user drag (position change via onNodesChange)", () => {
    const { setGraph, onNodesChange } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], []);
    expect(useFlowEditorStore.getState().dirty).toBe(false);

    const dragChanges: NodeChange<FlowNodeType>[] = [
      { id: "a", type: "position", position: { x: 42, y: 42 }, dragging: true },
    ];
    onNodesChange(dragChanges);

    expect(useFlowEditorStore.getState().dirty).toBe(true);
  });
});
