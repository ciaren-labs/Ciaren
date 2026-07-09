import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Position } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";
import { FlowEdge } from "../FlowEdge";
import { useFlowEditorStore, type FlowNodeType } from "@/stores/flowEditorStore";
import { useToastStore } from "@/stores/toastStore";

// EdgeLabelRenderer portals into a DOM node that only exists once a full
// <ReactFlow> instance has mounted (it queries the flow's own store for a
// `domNode`, set up by <ReactFlow> itself, not by <ReactFlowProvider> alone).
// BaseEdge and getSmoothStepPath are plain, hook-free functions, so the only
// thing standing between this component and a lightweight standalone render
// is that portal target — stub it to portal into document.body instead, same
// as production (where the target div is a *sibling* of the edges <svg>, not
// a descendant — rendering the label content as a child of <svg> would make
// jsdom/React create it in the SVG namespace, where `className` isn't a plain
// string, breaking every className assertion below).
vi.mock("@xyflow/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@xyflow/react")>();
  return {
    ...actual,
    EdgeLabelRenderer: ({ children }: { children: ReactNode }) => createPortal(children, document.body),
  };
});

function node(id: string): FlowNodeType {
  return { id, type: "dropNulls", position: { x: 0, y: 0 }, data: { label: id, config: {} } };
}

const baseProps = {
  id: "e1",
  source: "a",
  target: "b",
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: Position.Right,
  targetPosition: Position.Left,
} as unknown as EdgeProps;

function renderEdge(overrides: Partial<EdgeProps> = {}) {
  return render(
    <svg>
      <FlowEdge {...baseProps} {...overrides} />
    </svg>,
  );
}

describe("FlowEdge hover-delete button", () => {
  it("removes the edge from the store when clicked", async () => {
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );
    renderEdge();

    await user.click(screen.getByRole("button", { name: "Delete edge" }));

    expect(useFlowEditorStore.getState().edges).toHaveLength(0);
  });

  it("shows an undoable toast when deleted", async () => {
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );
    useToastStore.setState({ toasts: [] });
    renderEdge();

    await user.click(screen.getByRole("button", { name: "Delete edge" }));

    const [t] = useToastStore.getState().toasts;
    expect(t).toMatchObject({ variant: "success", title: "Connection deleted" });
    expect(t.action?.label).toBe("Undo");

    t.action?.onClick?.();
    expect(useFlowEditorStore.getState().edges).toHaveLength(1);
  });

  it("shows no toast if the edge was already removed by the time Delete is clicked", async () => {
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );
    useToastStore.setState({ toasts: [] });
    renderEdge();
    useFlowEditorStore.getState().removeEdge("e1");

    await user.click(screen.getByRole("button", { name: "Delete edge" }));

    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("renders no delete affordance when the edge is not deletable", () => {
    renderEdge({ deletable: false } as Partial<EdgeProps>);
    expect(screen.queryByRole("button", { name: "Delete edge" })).not.toBeInTheDocument();
  });

  it("is visible (not hidden behind opacity/pointer-events) when selected without hovering", () => {
    renderEdge({ selected: true } as Partial<EdgeProps>);
    const button = screen.getByRole("button", { name: "Delete edge" });
    const wrapper = button.parentElement as HTMLElement;
    expect(wrapper.className).toContain("opacity-100");
    expect(wrapper.className).toContain("pointer-events-auto");
  });

  it("is hidden (opacity-0, pointer-events-none) when neither selected nor hovered", () => {
    renderEdge();
    const button = screen.getByRole("button", { name: "Delete edge" });
    const wrapper = button.parentElement as HTMLElement;
    expect(wrapper.className).toContain("opacity-0");
    expect(wrapper.className).toContain("pointer-events-none");
  });

  it("reveals the button on hovering the invisible hit-path, and hides it again on mouse-leave", () => {
    const { container } = renderEdge();
    const button = screen.getByRole("button", { name: "Delete edge" });
    const wrapper = button.parentElement as HTMLElement;
    const hitPath = container.querySelector("path.cursor-pointer") as SVGPathElement;
    expect(wrapper.className).toContain("opacity-0");

    fireEvent.mouseEnter(hitPath);
    expect(wrapper.className).toContain("opacity-100");
    expect(wrapper.className).toContain("pointer-events-auto");

    fireEvent.mouseLeave(hitPath);
    expect(wrapper.className).toContain("opacity-0");
    expect(wrapper.className).toContain("pointer-events-none");
  });

  it("stays visible via focus-within when the button is focused directly (keyboard nav), even unhovered", () => {
    renderEdge();
    const button = screen.getByRole("button", { name: "Delete edge" });
    const wrapper = button.parentElement as HTMLElement;

    button.focus();

    // jsdom doesn't evaluate the `focus-within:` CSS variant itself, so this
    // only asserts the class is present for it to act on — the real browser
    // behavior (button visible while focused) depends on that class existing.
    expect(wrapper.className).toContain("focus-within:opacity-100");
    expect(wrapper.className).toContain("focus-within:pointer-events-auto");
    expect(button).toHaveFocus();
  });

  it("clicking the button does not bubble to an ancestor onClick", async () => {
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph(
      [node("a"), node("b")],
      [{ id: "e1", source: "a", target: "b" }],
    );
    let bubbled = false;
    render(
      <svg onClick={() => { bubbled = true; }}>
        <FlowEdge {...baseProps} />
      </svg>,
    );

    await user.click(screen.getByRole("button", { name: "Delete edge" }));

    expect(bubbled).toBe(false);
  });

  it("does nothing (no throw, no store change) if the edge was already removed elsewhere", async () => {
    const user = userEvent.setup();
    useFlowEditorStore.getState().reset();
    useFlowEditorStore.getState().setGraph([node("a"), node("b")], []);
    renderEdge();

    await user.click(screen.getByRole("button", { name: "Delete edge" }));

    expect(useFlowEditorStore.getState().edges).toHaveLength(0);
  });
});
