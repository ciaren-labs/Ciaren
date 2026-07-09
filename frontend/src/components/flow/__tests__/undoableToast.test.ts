import { beforeEach, describe, expect, it } from "vitest";
import { undoableToast } from "../undoableToast";
import { useFlowEditorStore, type FlowNodeType } from "@/stores/flowEditorStore";
import { useToastStore } from "@/stores/toastStore";

function node(id: string): FlowNodeType {
  return { id, type: "dropNulls", position: { x: 0, y: 0 }, data: { label: id, config: {} } };
}

describe("undoableToast", () => {
  beforeEach(() => {
    useFlowEditorStore.getState().reset();
    useToastStore.setState({ toasts: [] });
  });

  it("pushes a success toast with an Undo action that calls the store's undo", () => {
    useFlowEditorStore.getState().setGraph([node("a")], []);
    useFlowEditorStore.getState().removeNode("a");
    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);

    undoableToast("Node deleted");

    const [t] = useToastStore.getState().toasts;
    expect(t).toMatchObject({ variant: "success", title: "Node deleted" });
    expect(t.action?.label).toBe("Undo");

    t.action?.onClick?.();
    expect(useFlowEditorStore.getState().nodes).toHaveLength(1);
  });

  it("does nothing when Undo is clicked after the flow editor has been reset (session changed)", () => {
    useFlowEditorStore.getState().setGraph([node("a")], []);
    useFlowEditorStore.getState().removeNode("a");

    undoableToast("Node deleted");
    const [t] = useToastStore.getState().toasts;

    // Simulate navigating to a different flow: FlowEditorPage calls reset()
    // on its flow-id effect cleanup, then a fresh graph is loaded.
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph([node("b")], []);
    useFlowEditorStore.getState().removeNode("b");
    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);

    // Clicking the stale Undo from the first flow's toast must not resurrect
    // node "b" in the new flow, nor anything else — it should just no-op.
    t.action?.onClick?.();

    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);
  });

  it("still fires undo() normally when a same-session edit happens first (the accepted Ctrl+Z-style ambiguity)", () => {
    // Only a *session* change (reset(), i.e. switching flows) is guarded
    // against. A same-session stale Undo still fires — it just undoes
    // whatever's most recent, same as plain Ctrl+Z always has — so this only
    // asserts undo() actually ran (state changed), not which exact edit it
    // reverted (that's timing-sensitive: rapid same-kind edits can coalesce
    // into one history step, same as any other same-session undo).
    useFlowEditorStore.getState().setGraph([node("a"), node("b")], []);
    useFlowEditorStore.getState().removeNode("a");
    undoableToast("Node deleted");
    const [t] = useToastStore.getState().toasts;

    useFlowEditorStore.getState().removeNode("b");
    expect(useFlowEditorStore.getState().nodes).toHaveLength(0);

    t.action?.onClick?.();

    expect(useFlowEditorStore.getState().nodes.length).toBeGreaterThan(0);
  });
});
