import type { Edge, Node } from "@xyflow/react";

// Gaps between node *edges* (not centers). Real rendered sizes (not a fixed
// column width) keep large graphs compact; the gaps leave room for the animated
// smoothstep edges to curve without the nodes touching.
const MAIN_GAP = 43; // along the flow direction (between layers)
const CROSS_GAP = 26; // across the flow direction (between siblings)
const COMPACT_MAIN_GAP = 28;
const COMPACT_CROSS_GAP = 14;
// Fallbacks for nodes React Flow hasn't measured yet (e.g. just-created nodes).
const FALLBACK_W = 180;
const FALLBACK_H = 56;
// A multi-column edge is routed through thin "dummy" waypoints that reserve a
// lane in each column it crosses, so it never passes behind a node.
const DUMMY_THIN = 12;
const ORDER_SWEEPS = 4;
const POSITION_ITERS = 40;

/** The available auto-arrange layouts (kept in sync with the editor toolbar). */
export type LayoutKind = "horizontal" | "vertical" | "compact" | "tree" | "grid";

export interface LayoutOption {
  kind: LayoutKind;
  label: string;
  hint: string;
}

export const LAYOUT_OPTIONS: LayoutOption[] = [
  { kind: "horizontal", label: "Horizontal", hint: "Left → right (default)" },
  { kind: "vertical", label: "Vertical", hint: "Top → bottom, uses vertical space" },
  { kind: "compact", label: "Compact", hint: "Left → right, tighter spacing" },
  { kind: "tree", label: "Tree", hint: "Top → bottom, tight branches" },
  { kind: "grid", label: "Grid", hint: "Balanced, roughly square" },
];

interface LayeredOptions {
  direction: "LR" | "TB";
  mainGap: number;
  crossGap: number;
}

/** Dispatch to the requested layout. `horizontal` matches the historical layout. */
export function applyLayout<T extends Node>(kind: LayoutKind, nodes: T[], edges: Edge[]): T[] {
  switch (kind) {
    case "vertical":
      return layeredLayout(nodes, edges, { direction: "TB", mainGap: MAIN_GAP, crossGap: CROSS_GAP });
    case "compact":
      return layeredLayout(nodes, edges, { direction: "LR", mainGap: COMPACT_MAIN_GAP, crossGap: COMPACT_CROSS_GAP });
    case "tree":
      return layeredLayout(nodes, edges, { direction: "TB", mainGap: COMPACT_MAIN_GAP, crossGap: COMPACT_CROSS_GAP });
    case "grid":
      return gridLayout(nodes, edges);
    case "horizontal":
    default:
      return layeredLayout(nodes, edges, { direction: "LR", mainGap: MAIN_GAP, crossGap: CROSS_GAP });
  }
}

/** Back-compat: the default left-to-right layered layout. */
export function autoLayout<T extends Node>(nodes: T[], edges: Edge[]): T[] {
  return layeredLayout(nodes, edges, { direction: "LR", mainGap: MAIN_GAP, crossGap: CROSS_GAP });
}

/**
 * Layered ("Sugiyama style") auto-layout, parameterised by direction and gaps:
 *
 * 1. assign each node a layer = longest path from a source;
 * 2. insert dummy waypoints so an edge spanning N layers reserves a lane in each
 *    intermediate one (this is what stops edges crossing behind nodes);
 * 3. order each layer by the barycenter of its neighbours to reduce crossings;
 * 4. assign cross-axis positions that pull connected nodes into line while keeping
 *    a minimum gap, so the reserved lanes line up with where edges actually run.
 *
 * For "LR" the layer axis is x and the cross axis is y; for "TB" they swap.
 */
function layeredLayout<T extends Node>(nodes: T[], edges: Edge[], opts: LayeredOptions): T[] {
  if (nodes.length === 0) return nodes;
  const { direction, mainGap, crossGap } = opts;

  const realIds = new Set(nodes.map((n) => n.id));
  const realEdges = edges.filter((e) => realIds.has(e.source) && realIds.has(e.target));

  // 1) Layer = longest path from any source (Kahn / BFS over a DAG).
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

  // 2) Per-layer order lists + dummy waypoints for edges that span >1 layer.
  const order: string[][] = Array.from({ length: maxLayer + 1 }, () => []);
  for (const n of nodes) order[layer.get(n.id)!].push(n.id);

  const isDummy = new Set<string>();
  const upNb = new Map<string, string[]>(); // id -> neighbours in previous layer
  const downNb = new Map<string, string[]>(); // id -> neighbours in next layer
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
    if (lv <= lu) continue; // defensive: ignore same-layer / back edges
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
  const wOf = (id: string) => {
    const n = nodeById.get(id);
    return n?.measured?.width ?? n?.width ?? FALLBACK_W;
  };
  const hOf = (id: string) => {
    const n = nodeById.get(id);
    return n?.measured?.height ?? n?.height ?? FALLBACK_H;
  };
  // Extent along the layer axis (main) and across it (cross), per direction.
  const mainExtent = (id: string) =>
    isDummy.has(id) ? 0 : direction === "LR" ? wOf(id) : hOf(id);
  const crossExtent = (id: string) =>
    isDummy.has(id) ? DUMMY_THIN : direction === "LR" ? hOf(id) : wOf(id);

  // 3) Crossing reduction: sort each layer by the average index of its neighbours
  //    in the adjacent (already-ordered) layer, alternating sweeps.
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

  // 4a) main-axis position: cumulative layer extent (real nodes only).
  const layerMain: number[] = [];
  let m = 0;
  for (let l = 0; l <= maxLayer; l++) {
    layerMain[l] = m;
    const reals = order[l].filter((id) => !isDummy.has(id));
    m += (reals.length ? Math.max(...reals.map(mainExtent)) : 0) + mainGap;
  }

  // 4b) cross-axis centres: start from a centred stack, then one-sided median
  //     sweeps (down aligns to parents, up to children) projected back to a
  //     feasible, order-preserving column via isotonic regression.
  const cc = new Map<string, number>();
  for (let l = 0; l <= maxLayer; l++) {
    const ids = order[l];
    const total = ids.reduce((s, id) => s + crossExtent(id), 0) + crossGap * Math.max(ids.length - 1, 0);
    let top = -total / 2;
    for (const id of ids) {
      cc.set(id, top + crossExtent(id) / 2);
      top += crossExtent(id) + crossGap;
    }
  }
  const sep = (a: string, b: string) => crossExtent(a) / 2 + crossGap + crossExtent(b) / 2;
  const place = (l: number, nb: Map<string, string[]>) => {
    const ids = order[l];
    if (ids.length === 0) return;
    const desired = ids.map((id) => {
      const cs = (nb.get(id) ?? []).map((n) => cc.get(n)!);
      return cs.length ? median(cs) : cc.get(id)!;
    });
    const offset: number[] = [0];
    for (let i = 1; i < ids.length; i++) offset[i] = offset[i - 1] + sep(ids[i - 1], ids[i]);
    const fitted = isotonic(desired.map((d, i) => d - offset[i]));
    ids.forEach((id, i) => cc.set(id, fitted[i] + offset[i]));
  };
  for (let it = 0; it < POSITION_ITERS; it++) {
    if (it % 2 === 0) for (let l = 1; l <= maxLayer; l++) place(l, upNb);
    else for (let l = maxLayer - 1; l >= 0; l--) place(l, downNb);
  }

  const pos = new Map<string, { x: number; y: number }>();
  for (let l = 0; l <= maxLayer; l++) {
    for (const id of order[l]) {
      if (isDummy.has(id)) continue;
      const main = layerMain[l];
      const cross = cc.get(id)! - crossExtent(id) / 2;
      pos.set(id, direction === "LR" ? { x: main, y: cross } : { x: cross, y: main });
    }
  }

  return nodes.map((n) => {
    const p = pos.get(n.id);
    return p ? { ...n, position: p } : n;
  });
}

/**
 * Balanced grid: place nodes in topological order into a roughly-square grid so
 * neither dimension dominates. Good for many small, mostly-independent nodes.
 */
function gridLayout<T extends Node>(nodes: T[], edges: Edge[]): T[] {
  if (nodes.length === 0) return nodes;
  // Order by the layered layout's x so the grid still reads roughly source→sink.
  const laid = layeredLayout(nodes, edges, { direction: "LR", mainGap: MAIN_GAP, crossGap: CROSS_GAP });
  const ordered = [...laid].sort((a, b) => a.position.x - b.position.x || a.position.y - b.position.y);

  const cols = Math.max(1, Math.ceil(Math.sqrt(ordered.length)));
  const cellW = Math.max(...nodes.map((n) => n.measured?.width ?? n.width ?? FALLBACK_W)) + MAIN_GAP;
  const cellH = Math.max(...nodes.map((n) => n.measured?.height ?? n.height ?? FALLBACK_H)) + CROSS_GAP;

  const pos = new Map<string, { x: number; y: number }>();
  ordered.forEach((n, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    pos.set(n.id, { x: col * cellW, y: row * cellH });
  });
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
 * `values`, via pool-adjacent-violators. Used to project desired cross positions
 * back to a feasible, order-preserving column in O(n).
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
