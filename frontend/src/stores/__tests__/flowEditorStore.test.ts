import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

  it("removeNode is a no-op for an id that doesn't exist (no phantom undo entry, no dirty flip)", () => {
    // Reachable via a stale right-click context menu left open on a node that
    // gets deleted through some other path (its own hover-toolbar button,
    // Ctrl+Z) before the menu's Delete is clicked.
    const { setGraph, removeNode } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    removeNode("missing");

    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().dirty).toBe(false);
    expect(useFlowEditorStore.getState().past).toHaveLength(0);
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

  it("bumps sessionId only on reset, not on ordinary edits", () => {
    const { addNode, removeNode, setGraph, undo, reset } = useFlowEditorStore.getState();
    const initial = useFlowEditorStore.getState().sessionId;

    addNode(node("a"));
    removeNode("a");
    setGraph([node("b")], []);
    undo();
    expect(useFlowEditorStore.getState().sessionId).toBe(initial);

    reset();
    expect(useFlowEditorStore.getState().sessionId).toBe(initial + 1);
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

describe("flowEditorStore duplicateNode", () => {
  it("clones the node with a new id, offset position, and selects the copy", () => {
    const { setGraph, duplicateNode } = useFlowEditorStore.getState();
    setGraph([{ ...node("a", { value: "hello" }), position: { x: 10, y: 20 } }], []);

    duplicateNode("a");

    const { nodes, selectedNodeId, sidebarOpen } = useFlowEditorStore.getState();
    expect(nodes).toHaveLength(2);
    const clone = nodes.find((n) => n.id !== "a")!;
    expect(clone.id).not.toBe("a");
    expect(clone.data.config).toEqual({ value: "hello" });
    expect(clone.position).toEqual({ x: 42, y: 52 });
    expect(clone.selected).toBe(true);
    expect(nodes.find((n) => n.id === "a")!.selected).toBe(false);
    expect(selectedNodeId).toBe(clone.id);
    expect(sidebarOpen).toBe(true);
    expect(useFlowEditorStore.getState().dirty).toBe(true);
  });

  it("does not clone edges connected to the original node", () => {
    const { setGraph, duplicateNode } = useFlowEditorStore.getState();
    setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );

    duplicateNode("a");

    expect(useFlowEditorStore.getState().edges).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes).toHaveLength(3);
  });

  it("is undoable", () => {
    const { setGraph, duplicateNode, undo } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    duplicateNode("a");
    expect(useFlowEditorStore.getState().nodes).toHaveLength(2);

    undo();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].id).toBe("a");
  });

  it("is a no-op for an id that doesn't exist", () => {
    const { setGraph, duplicateNode } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    duplicateNode("missing");

    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().dirty).toBe(false);
    expect(useFlowEditorStore.getState().past).toHaveLength(0);
  });
});

describe("flowEditorStore removeEdge", () => {
  it("removes only the targeted edge, leaving nodes and other edges intact", () => {
    const { setGraph, removeEdge } = useFlowEditorStore.getState();
    setGraph(
      [node("a"), node("b"), node("c")],
      [
        { id: "e1", source: "a", target: "b" },
        { id: "e2", source: "b", target: "c" },
      ],
    );

    removeEdge("e1");

    const { edges, nodes, dirty } = useFlowEditorStore.getState();
    expect(edges).toEqual([{ id: "e2", source: "b", target: "c" }]);
    expect(nodes).toHaveLength(3);
    expect(dirty).toBe(true);
  });

  it("is undoable", () => {
    const { setGraph, removeEdge, undo } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], [{ id: "e1", source: "a", target: "b" }]);

    removeEdge("e1");
    expect(useFlowEditorStore.getState().edges).toHaveLength(0);

    undo();
    expect(useFlowEditorStore.getState().edges).toHaveLength(1);
  });

  it("is a no-op for an id that doesn't exist", () => {
    const { setGraph, removeEdge } = useFlowEditorStore.getState();
    setGraph([node("a"), node("b")], [{ id: "e1", source: "a", target: "b" }]);

    removeEdge("missing");

    expect(useFlowEditorStore.getState().edges).toHaveLength(1);
    expect(useFlowEditorStore.getState().dirty).toBe(false);
    expect(useFlowEditorStore.getState().past).toHaveLength(0);
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

describe("flowEditorStore pasteSelection", () => {
  it("appends the pasted nodes/edges, deselects the originals, and is one undo step", () => {
    const { setGraph, pasteSelection, undo } = useFlowEditorStore.getState();
    setGraph(
      [{ ...node("a"), selected: true }, { ...node("b"), selected: true }],
      [{ id: "e1", source: "a", target: "b" }],
    );

    const pastedA = { ...node("a2"), selected: true };
    const pastedB = { ...node("b2"), selected: true };
    pasteSelection([pastedA, pastedB], [{ id: "e2", source: "a2", target: "b2" }]);

    const { nodes, edges, past, dirty } = useFlowEditorStore.getState();
    expect(nodes).toHaveLength(4);
    expect(edges).toHaveLength(2);
    // Originals are deselected so the pasted copy becomes the active selection.
    expect(nodes.find((n) => n.id === "a")!.selected).toBe(false);
    expect(nodes.find((n) => n.id === "b")!.selected).toBe(false);
    expect(nodes.find((n) => n.id === "a2")!.selected).toBe(true);
    expect(dirty).toBe(true);
    expect(past).toHaveLength(1);

    undo();
    const after = useFlowEditorStore.getState();
    expect(after.nodes).toHaveLength(2);
    expect(after.edges).toHaveLength(1);
  });

  it("pasting an empty selection is still a no-op-shaped call (no nodes added) but still checkpoints", () => {
    // Guards against a stale/empty clipboard producing a corrupt undo entry:
    // the graph must come back unchanged, not lose the original nodes.
    const { setGraph, pasteSelection } = useFlowEditorStore.getState();
    setGraph([node("a")], []);

    pasteSelection([], []);

    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].id).toBe("a");
    expect(useFlowEditorStore.getState().past).toHaveLength(1);
  });
});

describe("flowEditorStore patchMultipleNodeConfigs", () => {
  it("patches only the nodes named in the patch map, in a single undo step", () => {
    const { setGraph, patchMultipleNodeConfigs, undo } = useFlowEditorStore.getState();
    setGraph(
      [node("a", { x: 1 }), node("b", { x: 2 }), node("c", { x: 3 })],
      [],
    );

    patchMultipleNodeConfigs({ a: { x: 10 }, c: { x: 30 } });

    const { nodes, past } = useFlowEditorStore.getState();
    expect(nodes.find((n) => n.id === "a")!.data.config).toEqual({ x: 10 });
    expect(nodes.find((n) => n.id === "b")!.data.config).toEqual({ x: 2 });
    expect(nodes.find((n) => n.id === "c")!.data.config).toEqual({ x: 30 });
    expect(past).toHaveLength(1);

    undo();
    const after = useFlowEditorStore.getState();
    expect(after.nodes.find((n) => n.id === "a")!.data.config).toEqual({ x: 1 });
    expect(after.nodes.find((n) => n.id === "c")!.data.config).toEqual({ x: 3 });
  });

  it("replaces a node's config wholesale rather than merging the patch", () => {
    const { setGraph, patchMultipleNodeConfigs } = useFlowEditorStore.getState();
    setGraph([node("a", { x: 1, y: 2, label: "kept?" })], []);

    // A patch that omits `y`/`label` must drop them, not merge over them —
    // config forms send the full replacement config on every save.
    patchMultipleNodeConfigs({ a: { x: 99 } });

    expect(useFlowEditorStore.getState().nodes[0].data.config).toEqual({ x: 99 });
  });
});

describe("flowEditorStore history-stack cap", () => {
  // Each checkpoint key embeds Date.now(), so two calls landing in the same
  // millisecond (routine in a tight synchronous loop) would otherwise
  // coalesce into one step, same as real edits within the 700ms window.
  // Fake timers space every addNode out past COALESCE_WINDOW_MS so each one
  // is guaranteed its own undo entry, matching how a long real editing
  // session actually accumulates history.
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("caps the undo stack at HISTORY_LIMIT (50), dropping the oldest entries", () => {
    const { setGraph, addNode } = useFlowEditorStore.getState();
    setGraph([], []);

    for (let i = 0; i < 60; i++) {
      addNode(node(`n${i}`));
      vi.advanceTimersByTime(1000);
    }

    expect(useFlowEditorStore.getState().past).toHaveLength(50);
    expect(useFlowEditorStore.getState().nodes).toHaveLength(60);
  });

  it("caps the redo stack at HISTORY_LIMIT too", () => {
    const { setGraph, addNode, undo } = useFlowEditorStore.getState();
    setGraph([], []);

    for (let i = 0; i < 60; i++) {
      addNode(node(`n${i}`));
      vi.advanceTimersByTime(1000);
    }
    for (let i = 0; i < 60; i++) {
      undo();
    }

    // 60 adds cap `past` at 50; 50 undos drain it to empty while filling
    // `future` to exactly 50, then 10 more undos are no-ops on an empty
    // `past` — future must stay capped at 50, not keep growing.
    expect(useFlowEditorStore.getState().future).toHaveLength(50);
  });
});

describe("flowEditorStore undo/redo interaction with coalescing", () => {
  it("does not let an edit after undo coalesce with the pre-undo edit group", () => {
    // Regression guard: undo() resets historyGroupKey/historyGroupAt. Without
    // that reset, typing in the same field right after an undo could silently
    // merge into the (now-discarded) pre-undo group instead of starting a
    // fresh, independently-undoable step.
    const { setGraph, updateNodeConfig, undo } = useFlowEditorStore.getState();
    setGraph([node("a", { value: "" })], []);

    updateNodeConfig("a", { value: "first" });
    expect(useFlowEditorStore.getState().past).toHaveLength(1);

    undo();
    expect(useFlowEditorStore.getState().nodes[0].data.config.value).toBe("");
    expect(useFlowEditorStore.getState().past).toHaveLength(0);

    updateNodeConfig("a", { value: "second" });
    expect(useFlowEditorStore.getState().past).toHaveLength(1);
    expect(useFlowEditorStore.getState().nodes[0].data.config.value).toBe("second");

    undo();
    expect(useFlowEditorStore.getState().nodes[0].data.config.value).toBe("");
  });

  it("clears selectedNodeId on both undo and redo", () => {
    const { setGraph, addNode, selectNode, undo, redo } = useFlowEditorStore.getState();
    setGraph([node("a")], []);
    addNode(node("b"));
    selectNode("b");
    expect(useFlowEditorStore.getState().selectedNodeId).toBe("b");

    undo();
    expect(useFlowEditorStore.getState().selectedNodeId).toBeNull();

    selectNode("a");
    redo();
    expect(useFlowEditorStore.getState().selectedNodeId).toBeNull();
  });
});
