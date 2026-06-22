import type { Edge, Node } from "@xyflow/react";

const COL_WIDTH = 260;
const ROW_HEIGHT = 110;

/**
 * Arranges nodes left-to-right by topological level (BFS from sources).
 * Returns new nodes with updated positions; edges and node data are untouched.
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

  // BFS: assign column = max distance from any source
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
  // Disconnected nodes fall into column 0
  for (const n of nodes) {
    if (!col.has(n.id)) col.set(n.id, 0);
  }

  // Group by column
  const byCol = new Map<number, string[]>();
  for (const [id, c] of col) {
    byCol.set(c, [...(byCol.get(c) ?? []), id]);
  }

  // Assign positions centered vertically per column
  const pos = new Map<string, { x: number; y: number }>();
  for (const [c, ids] of byCol) {
    const x = c * COL_WIDTH;
    const totalH = ids.length * ROW_HEIGHT;
    ids.forEach((id, i) => {
      pos.set(id, { x, y: i * ROW_HEIGHT - totalH / 2 });
    });
  }

  return nodes.map((n) => {
    const p = pos.get(n.id);
    return p ? { ...n, position: p } : n;
  });
}
