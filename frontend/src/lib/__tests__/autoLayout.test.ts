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

type Pt = { x: number; y: number };
type Box = { x: number; y: number; w: number; h: number };

function boxOf(n: Node): Box {
  return {
    x: n.position.x,
    y: n.position.y,
    w: (n.measured?.width ?? 180) as number,
    h: (n.measured?.height ?? 56) as number,
  };
}

function segsCross(a: Pt, b: Pt, c: Pt, d: Pt): boolean {
  const o = (p: Pt, q: Pt, r: Pt) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
  const d1 = o(c, d, a);
  const d2 = o(c, d, b);
  const d3 = o(a, b, c);
  const d4 = o(a, b, d);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

/** Does the segment p->q cross (or start/end inside) an axis-aligned box? */
function segHitsBox(p: Pt, q: Pt, b: Box): boolean {
  const inside = (pt: Pt) => pt.x > b.x && pt.x < b.x + b.w && pt.y > b.y && pt.y < b.y + b.h;
  if (inside(p) || inside(q)) return true;
  const tl = { x: b.x, y: b.y };
  const tr = { x: b.x + b.w, y: b.y };
  const br = { x: b.x + b.w, y: b.y + b.h };
  const bl = { x: b.x, y: b.y + b.h };
  return (
    segsCross(p, q, tl, tr) ||
    segsCross(p, q, tr, br) ||
    segsCross(p, q, br, bl) ||
    segsCross(p, q, bl, tl)
  );
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
    expect(Math.abs(pos.get("b")!.y - pos.get("a")!.y)).toBe(56 + 26);
  });

  it("falls back to default sizes for unmeasured nodes without overlapping", () => {
    const unmeasured = { id: "a", position: { x: 0, y: 0 }, data: {} } as Node;
    const pos = posById(autoLayout([unmeasured, node("b")], [edge("a", "b")]));
    expect(pos.get("b")!.x).toBeGreaterThan(pos.get("a")!.x + 100);
  });

  it("does not route a column-spanning edge behind a node (full sales mart)", () => {
    // orders -> dedup -> j2 makes dedup->j2 span j1's column — the case that
    // used to draw an edge behind the join node.
    const ids = ["items", "products", "orders", "calc", "fill", "j1", "dedup", "j2", "grp", "cond", "out"];
    const nodes = ids.map((id) => node(id));
    const edges = [
      edge("items", "calc"),
      edge("calc", "j1"),
      edge("products", "fill"),
      edge("fill", "j1"),
      edge("j1", "j2"),
      edge("orders", "dedup"),
      edge("dedup", "j2"),
      edge("j2", "grp"),
      edge("grp", "cond"),
      edge("cond", "out"),
    ];

    const laid = autoLayout(nodes, edges);
    const byId = new Map(laid.map((n) => [n.id, n]));

    // Every edge runs from a source's right side to a target's left side; none
    // may pass through any node that isn't its own endpoint.
    for (const e of edges) {
      const s = boxOf(byId.get(e.source)!);
      const t = boxOf(byId.get(e.target)!);
      const p = { x: s.x + s.w, y: s.y + s.h / 2 };
      const q = { x: t.x, y: t.y + t.h / 2 };
      for (const other of laid) {
        if (other.id === e.source || other.id === e.target) continue;
        expect(segHitsBox(p, q, boxOf(other))).toBe(false);
      }
    }

    // And no two nodes overlap.
    for (let i = 0; i < laid.length; i++) {
      for (let j = i + 1; j < laid.length; j++) {
        const a = boxOf(laid[i]);
        const b = boxOf(laid[j]);
        const overlap = a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
        expect(overlap).toBe(false);
      }
    }

    // A 1-to-1 chain (the join -> group -> condition -> output tail) should sit
    // on one horizontal line — connected single-neighbour nodes must align.
    const centerY = (id: string) => {
      const b = boxOf(byId.get(id)!);
      return b.y + b.h / 2;
    };
    for (const id of ["grp", "cond", "out"]) {
      expect(Math.abs(centerY(id) - centerY("j2"))).toBeLessThan(0.5);
    }
  });

  it("aligns a 1-to-1 link even when each node shares its column", () => {
    // a->c and b->d are independent 1-to-1 links; each pair must line up.
    const nodes = [node("a"), node("b"), node("c"), node("d")];
    const edges = [edge("a", "c"), edge("b", "d")];
    const laid = autoLayout(nodes, edges);
    const cy = (id: string) => {
      const n = laid.find((m) => m.id === id)!;
      return n.position.y + 56 / 2;
    };
    expect(Math.abs(cy("a") - cy("c"))).toBeLessThan(0.5);
    expect(Math.abs(cy("b") - cy("d"))).toBeLessThan(0.5);
  });
});
