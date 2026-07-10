// Copy/paste id remapping: fresh ids, internal edges only, deep-copied
// configs, offset positions, pasted copy becomes the selection.
import { describe, expect, it } from "vitest";
import { cloneSelection } from "../flowGraph";

const node = (id: string, config: Record<string, unknown> = {}) => ({
  id,
  type: "filterRows",
  position: { x: 100, y: 200 },
  selected: true,
  data: { config },
});

const edge = (id: string, source: string, target: string, extra: Record<string, unknown> = {}) => ({
  id,
  source,
  target,
  ...extra,
});

describe("cloneSelection", () => {
  it("assigns fresh ids and remaps internal edges", () => {
    const nodes = [node("filterRows_1"), node("sortRows_2")];
    const edges = [edge("e1", "filterRows_1", "sortRows_2", { targetHandle: "in" })];
    const cloned = cloneSelection(nodes, edges);

    expect(cloned.nodes).toHaveLength(2);
    const [a, b] = cloned.nodes;
    expect(a.id).not.toBe("filterRows_1");
    expect(b.id).not.toBe("sortRows_2");
    expect(new Set(cloned.nodes.map((n) => n.id)).size).toBe(2);

    expect(cloned.edges).toHaveLength(1);
    expect(cloned.edges[0].source).toBe(a.id);
    expect(cloned.edges[0].target).toBe(b.id);
    expect(cloned.edges[0].id).not.toBe("e1");
    expect((cloned.edges[0] as Record<string, unknown>).targetHandle).toBe("in");
  });

  it("drops edges whose endpoints are outside the selection", () => {
    const nodes = [node("a_1")];
    const edges = [edge("e1", "outside", "a_1"), edge("e2", "a_1", "outside")];
    expect(cloneSelection(nodes, edges).edges).toEqual([]);
  });

  it("deep-copies configs so editing the paste can't mutate the original", () => {
    const original = node("a_1", { columns: ["x"] });
    const cloned = cloneSelection([original], []);
    (cloned.nodes[0].data.config.columns as string[]).push("y");
    expect(original.data.config.columns).toEqual(["x"]);
  });

  it("offsets positions and marks pasted nodes selected", () => {
    const cloned = cloneSelection([{ ...node("a_1"), selected: false }], [], 40);
    expect(cloned.nodes[0].position).toEqual({ x: 140, y: 240 });
    expect(cloned.nodes[0].selected).toBe(true);
  });

  it("consecutive pastes never collide ids", () => {
    const nodes = [node("a_1")];
    const first = cloneSelection(nodes, []);
    const second = cloneSelection(nodes, []);
    expect(first.nodes[0].id).not.toBe(second.nodes[0].id);
  });
});
