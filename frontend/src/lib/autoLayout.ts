import type { Edge, Node } from "@xyflow/react";

// Gaps between node *edges* (not centers). Real rendered sizes (not a fixed
// column width) keep large graphs compact; the gaps leave room for the animated
// smoothstep edges to curve without the nodes touching.
const H_GAP = 43;
const V_GAP = 26;
// Fallbacks for nodes React Flow hasn't measured yet (e.g. just-created nodes).
const FALLBACK_W = 180;
const FALLBACK_H = 56;
// A multi-column edge is routed through thin "dummy" waypoints that reserve a
// vertical lane in each column it crosses, so it never passes behind a node.
const DUMMY_H = 12;
const ORDER_SWEEPS = 4;
const POSITION_ITERS = 40;

/**
 * Layered ("Sugiyama style") left-to-right auto-layout:
 *
 * 1. assign each node a column = longest path from a source;
 * 2. insert dummy waypoints so an edge spanning N columns reserves a lane in
 *    each intermediate one (this is what stops edges crossing behind nodes);
 * 3. order each column by the barycenter of its neighbours to reduce crossings;
 * 4. assign vertical positions that pull connected nodes into line while keeping
 *    a minimum gap, so the reserved lanes line up with where edges actually run.
 *
 * Returns new nodes with updated positions; edges and node data are untouched.
 */
export function autoLayout<T extends Node>(nodes: T[], edges: Edge[]): T[] {
  if (nodes.length === 0) return nodes;

  const realIds = new Set(nodes.map((n) => n.id));
  const realEdges = edges.filter((e) => realIds.has(e.source) && realIds.has(e.target));

  // 1) Column = longest path from any source (Kahn / BFS over a DAG).
  const adj = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    inDegree.set(n.id, 0);
  }
  for (const e of realEdges) {
    adj.get(e.source)!.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
  }
  const layer = new Map<string, number>();
  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) {
      queue.push(id);
      layer.set(id, 0);
    }
  }
  const remaining = new Map(inDegree);
  while (queue.length > 0) {
    const id = queue.shift()!;
    const level = layer.get(id)!;
    for (const neighbor of adj.get(id)!) {
      layer.set(neighbor, Math.max(layer.get(neighbor) ?? 0, level + 1));
      remaining.set(neighbor, (remaining.get(neighbor) ?? 1) - 1);
      if (remaining.get(neighbor) === 0) queue.push(neighbor);
    }
  }
  for (const n of nodes) if (!layer.has(n.id)) layer.set(n.id, 0); // islands / cycles
  const maxLayer = Math.max(...nodes.map((n) => layer.get(n.id)!));

  // 2) Per-column order lists + dummy waypoints for edges that span >1 column.
  const order: string[][] = Array.from({ length: maxLayer + 1 }, () => []);
  for (const n of nodes) order[layer.get(n.id)!].push(n.id);

  const isDummy = new Set<string>();
  const upNb = new Map<string, string[]>(); // id -> neighbours in previous column
  const downNb = new Map<string, string[]>(); // id -> neighbours in next column
  const push = (m: Map<string, string[]>, k: string, v: string) => {
    const arr = m.get(k);
    if (arr) arr.push(v);
    else m.set(k, [v]);
  };
  const link = (a: string, b: string) => {
    push(downNb, a, b);
    push(upNb, b, a);
  };

  let dummyCount = 0;
  for (const e of realEdges) {
    const lu = layer.get(e.source)!;
    const lv = layer.get(e.target)!;
    if (lv <= lu) continue; // defensive: ignore same-column / back edges
    if (lv === lu + 1) {
      link(e.source, e.target);
      continue;
    }
    let prev = e.source;
    for (let l = lu + 1; l < lv; l++) {
      const d = `__dummy_${dummyCount++}`;
      isDummy.add(d);
      order[l].push(d);
      link(prev, d);
      prev = d;
    }
    link(prev, e.target);
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const widthOf = (id: string) => {
    const n = nodeById.get(id);
    return n?.measured?.width ?? n?.width ?? FALLBACK_W;
  };
  const heightOf = (id: string) =>
    isDummy.has(id) ? DUMMY_H : (nodeById.get(id)?.measured?.height ?? nodeById.get(id)?.height ?? FALLBACK_H);

  // 3) Crossing reduction: sort each column by the average index of its
  //    neighbours in the adjacent (already-ordered) column, alternating sweeps.
  const indexMap = (l: number) => {
    const m = new Map<string, number>();
    order[l].forEach((id, i) => m.set(id, i));
    return m;
  };
  const sweep = (l: number, nb: Map<string, string[]>, refIdx: Map<string, number>) => {
    const bary = new Map<string, number>();
    order[l].forEach((id, i) => {
      const idxs = (nb.get(id) ?? []).map((n) => refIdx.get(n)).filter((v): v is number => v !== undefined);
      bary.set(id, idxs.length ? idxs.reduce((a, b) => a + b, 0) / idxs.length : i);
    });
    order[l] = [...order[l]].sort((a, b) => bary.get(a)! - bary.get(b)!);
  };
  for (let s = 0; s < ORDER_SWEEPS; s++) {
    if (s % 2 === 0) {
      for (let l = 1; l <= maxLayer; l++) sweep(l, upNb, indexMap(l - 1));
    } else {
      for (let l = maxLayer - 1; l >= 0; l--) sweep(l, downNb, indexMap(l + 1));
    }
  }

  // 4a) x: cumulative column width (real nodes only; dummies are zero-width).
  const colX: number[] = [];
  let x = 0;
  for (let l = 0; l <= maxLayer; l++) {
    colX[l] = x;
    const reals = order[l].filter((id) => !isDummy.has(id));
    x += (reals.length ? Math.max(...reals.map(widthOf)) : 0) + H_GAP;
  }

  // 4b) y (centres): start from a centred stack, then sweep one side at a time —
  //     downward aligns each node to the median of its parents, upward to the
  //     median of its children — projecting back to a feasible, order-preserving
  //     column via isotonic regression. One-sided median sweeps straighten 1-to-1
  //     chains and the dummy lanes exactly, so connected nodes line up instead of
  //     drifting a few pixels (which a two-sided average leaves behind).
  const cy = new Map<string, number>();
  for (let l = 0; l <= maxLayer; l++) {
    const ids = order[l];
    const total = ids.reduce((s, id) => s + heightOf(id), 0) + V_GAP * Math.max(ids.length - 1, 0);
    let top = -total / 2;
    for (const id of ids) {
      cy.set(id, top + heightOf(id) / 2);
      top += heightOf(id) + V_GAP;
    }
  }
  const sep = (a: string, b: string) => heightOf(a) / 2 + V_GAP + heightOf(b) / 2;
  const place = (l: number, nb: Map<string, string[]>) => {
    const ids = order[l];
    if (ids.length === 0) return;
    const desired = ids.map((id) => {
      const ys = (nb.get(id) ?? []).map((n) => cy.get(n)!);
      return ys.length ? median(ys) : cy.get(id)!;
    });
    // Minimum cumulative offset so consecutive centres keep their gaps.
    const offset: number[] = [0];
    for (let i = 1; i < ids.length; i++) offset[i] = offset[i - 1] + sep(ids[i - 1], ids[i]);
    const fitted = isotonic(desired.map((d, i) => d - offset[i]));
    ids.forEach((id, i) => cy.set(id, fitted[i] + offset[i]));
  };
  for (let it = 0; it < POSITION_ITERS; it++) {
    if (it % 2 === 0) for (let l = 1; l <= maxLayer; l++) place(l, upNb);
    else for (let l = maxLayer - 1; l >= 0; l--) place(l, downNb);
  }

  const pos = new Map<string, { x: number; y: number }>();
  for (let l = 0; l <= maxLayer; l++) {
    for (const id of order[l]) {
      if (!isDummy.has(id)) pos.set(id, { x: colX[l], y: cy.get(id)! - heightOf(id) / 2 });
    }
  }

  return nodes.map((n) => {
    const p = pos.get(n.id);
    return p ? { ...n, position: p } : n;
  });
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Isotonic regression: the non-decreasing sequence closest (least squares) to
 * `values`, via pool-adjacent-violators. Used to project desired vertical
 * positions back to a feasible, order-preserving column in O(n).
 */
function isotonic(values: number[]): number[] {
  const vals: number[] = [];
  const weights: number[] = [];
  const counts: number[] = [];
  for (const value of values) {
    let v = value;
    let w = 1;
    let c = 1;
    while (vals.length > 0 && vals[vals.length - 1] > v) {
      const pv = vals.pop()!;
      const pw = weights.pop()!;
      const pc = counts.pop()!;
      v = (v * w + pv * pw) / (w + pw);
      w += pw;
      c += pc;
    }
    vals.push(v);
    weights.push(w);
    counts.push(c);
  }
  const out: number[] = [];
  for (let b = 0; b < vals.length; b++) {
    for (let k = 0; k < counts[b]; k++) out.push(vals[b]);
  }
  return out;
}
