import type { Edge, Node } from "@xyflow/react";

// Gaps between node *edges* (not centers). Using the real rendered size of each
// node — instead of a fixed column width — keeps large graphs compact: a column
// of narrow nodes packs tightly, while a wide label only widens its own column.
// The gaps leave room for the animated smoothstep edges to curve cleanly without
// the nodes touching.
const H_GAP = 54;
const V_GAP = 32;
// Fallbacks for nodes React Flow hasn't measured yet (e.g. just-created nodes).
const FALLBACK_W = 180;
const FALLBACK_H = 56;

/**
 * Arranges nodes left-to-right by topological level (BFS from sources), packing
 * each level into a column sized to its widest node. Returns new nodes with
 * updated positions; edges and node data are untouched.
 */
export function autoLayout<T extends Node>(nodes: T[], edges: Edge[]): T[] {
  if (nodes.length === 0) return nodes;

  const adj = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    inDegree.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.source)?.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
  }

  // BFS: assign column = max distance from any source.
  const col = new Map<string, number>();
  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) {
      queue.push(id);
      col.set(id, 0);
    }
  }
  const remaining = new Map(inDegree);
  while (queue.length > 0) {
    const id = queue.shift()!;
    const level = col.get(id) ?? 0;
    for (const neighbor of adj.get(id) ?? []) {
      const next = Math.max(col.get(neighbor) ?? 0, level + 1);
      col.set(neighbor, next);
      remaining.set(neighbor, (remaining.get(neighbor) ?? 1) - 1);
      if (remaining.get(neighbor) === 0) queue.push(neighbor);
    }
  }
  // Disconnected nodes fall into column 0.
  for (const n of nodes) {
    if (!col.has(n.id)) col.set(n.id, 0);
  }

  // Group node ids by column, preserving array order for stable stacking.
  const byCol = new Map<number, string[]>();
  for (const n of nodes) {
    const c = col.get(n.id) ?? 0;
    byCol.set(c, [...(byCol.get(c) ?? []), n.id]);
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const widthOf = (id: string) => {
    const n = nodeById.get(id);
    return n?.measured?.width ?? n?.width ?? FALLBACK_W;
  };
  const heightOf = (id: string) => {
    const n = nodeById.get(id);
    return n?.measured?.height ?? n?.height ?? FALLBACK_H;
  };

  // Left x of each column = cumulative width of prior columns + gaps, so spacing
  // adapts to how wide each column's nodes actually are.
  const sortedCols = [...byCol.keys()].sort((a, b) => a - b);
  const colX = new Map<number, number>();
  let x = 0;
  for (const c of sortedCols) {
    colX.set(c, x);
    const colWidth = Math.max(...byCol.get(c)!.map(widthOf));
    x += colWidth + H_GAP;
  }

  // Within a column, stack nodes by their real height, centered vertically.
  const pos = new Map<string, { x: number; y: number }>();
  for (const c of sortedCols) {
    const ids = byCol.get(c)!;
    const heights = ids.map(heightOf);
    const totalH =
      heights.reduce((sum, h) => sum + h, 0) + V_GAP * (ids.length - 1);
    let y = -totalH / 2;
    ids.forEach((id, i) => {
      pos.set(id, { x: colX.get(c)!, y });
      y += heights[i] + V_GAP;
    });
  }

  return nodes.map((n) => {
    const p = pos.get(n.id);
    return p ? { ...n, position: p } : n;
  });
}
