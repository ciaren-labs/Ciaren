import { describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";
import { autoLayout } from "../autoLayout";

// Minimal node with a known rendered size, as React Flow reports via `measured`.
function node(id: string, width = 180, height = 56): Node {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {},
    measured: { width, height },
  } as Node;
}

function edge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target };
}

function posById(nodes: Node[]) {
  return new Map(nodes.map((n) => [n.id, n.position]));
}

describe("autoLayout", () => {
  it("places a linear chain left to right with no horizontal overlap", () => {
    const nodes = [node("a", 200), node("b", 180), node("c", 160)];
    const edges = [edge("a", "b"), edge("b", "c")];

    const pos = posById(autoLayout(nodes, edges));

    // Each column starts past the previous node's right edge (a real gap).
    expect(pos.get("b")!.x).toBeGreaterThan(pos.get("a")!.x + 200);
    expect(pos.get("c")!.x).toBeGreaterThan(pos.get("b")!.x + 180);
  });

  it("sizes each column to its own nodes, not a fixed width", () => {
    const wide = posById(autoLayout([node("a", 300), node("b", 180)], [edge("a", "b")]));
    const narrow = posById(autoLayout([node("a", 150), node("b", 180)], [edge("a", "b")]));

    // A wider source column pushes the next column further right.
    expect(wide.get("b")!.x).toBeGreaterThan(narrow.get("b")!.x);
    // ...by exactly the difference in source width (150px).
    expect(wide.get("b")!.x - narrow.get("b")!.x).toBe(150);
  });

  it("keeps a gap but stays compact (tighter than the old 260px columns)", () => {
    const pos = posById(autoLayout([node("a", 180), node("b", 180)], [edge("a", "b")]));
    const gap = pos.get("b")!.x - (pos.get("a")!.x + 180);
    expect(gap).toBeGreaterThan(0); // never touching
    expect(pos.get("b")!.x).toBeLessThan(260); // tighter than the previous layout
  });

  it("stacks a fan-in's target after both sources, centered", () => {
    const nodes = [node("a"), node("b"), node("c")];
    const edges = [edge("a", "c"), edge("b", "c")];

    const pos = posById(autoLayout(nodes, edges));

    // a and b are sources (column 0); c is downstream (column 1).
    expect(pos.get("a")!.x).toBe(pos.get("b")!.x);
    expect(pos.get("c")!.x).toBeGreaterThan(pos.get("a")!.x);
    // Two stacked nodes are separated by their height + the vertical gap, no overlap.
    expect(Math.abs(pos.get("b")!.y - pos.get("a")!.y)).toBe(56 + 32);
  });

  it("falls back to default sizes for unmeasured nodes without overlapping", () => {
    const unmeasured = { id: "a", position: { x: 0, y: 0 }, data: {} } as Node;
    const pos = posById(autoLayout([unmeasured, node("b")], [edge("a", "b")]));
    expect(pos.get("b")!.x).toBeGreaterThan(pos.get("a")!.x + 100);
  });
});
