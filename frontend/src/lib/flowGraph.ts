// Pure graph helpers shared by the editor: topological ordering and
// column-schema propagation. These have no React/xyflow dependencies so they
// can be unit-tested in isolation and reused by the validation layer.

import type { Dataset, DatasetSourceType } from "./types";

/** Minimal structural shapes — the zustand store's nodes/edges satisfy these. */
export interface GraphNodeLike {
  id: string;
  type?: string;
  data: { config: Record<string, unknown> };
}

export interface GraphEdgeLike {
  source: string;
  target: string;
  targetHandle?: string | null;
}

/** Input node type -> the dataset source_type it is allowed to read. */
export const INPUT_SOURCE_TYPE: Record<string, DatasetSourceType> = {
  csvInput: "csv",
  excelInput: "excel",
  parquetInput: "parquet",
};

export function isInputType(type: string | undefined): boolean {
  return type ? type in INPUT_SOURCE_TYPE : false;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

/**
 * Compute incoming edges grouped by target node id. Each entry preserves the
 * targetHandle so multi-input nodes (join left/right) can be distinguished.
 */
function incomingByTarget(
  edges: GraphEdgeLike[],
): Map<string, { source: string; handle: string }[]> {
  const map = new Map<string, { source: string; handle: string }[]>();
  for (const e of edges) {
    const list = map.get(e.target) ?? [];
    list.push({ source: e.source, handle: e.targetHandle ?? "in" });
    map.set(e.target, list);
  }
  return map;
}

/**
 * Return node ids in topological order. On a cycle the remaining nodes are
 * appended in their original order so callers still get every node back
 * (cycle detection itself is handled by the validation layer).
 */
export function topologicalOrder(
  nodes: GraphNodeLike[],
  edges: GraphEdgeLike[],
): string[] {
  const incoming = incomingByTarget(edges);
  const indegree = new Map<string, number>();
  for (const n of nodes) indegree.set(n.id, incoming.get(n.id)?.length ?? 0);

  const queue = nodes.filter((n) => (indegree.get(n.id) ?? 0) === 0).map((n) => n.id);
  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    const list = outgoing.get(e.source) ?? [];
    list.push(e.target);
    outgoing.set(e.source, list);
  }

  const order: string[] = [];
  const seen = new Set<string>();
  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    order.push(id);
    for (const next of outgoing.get(id) ?? []) {
      indegree.set(next, (indegree.get(next) ?? 1) - 1);
      if ((indegree.get(next) ?? 0) <= 0) queue.push(next);
    }
  }
  // Append any nodes left out by a cycle, in declaration order.
  for (const n of nodes) if (!seen.has(n.id)) order.push(n.id);
  return order;
}

/** Detect whether the graph contains a directed cycle. */
export function hasCycle(nodes: GraphNodeLike[], edges: GraphEdgeLike[]): boolean {
  const incoming = incomingByTarget(edges);
  const indegree = new Map<string, number>();
  for (const n of nodes) indegree.set(n.id, incoming.get(n.id)?.length ?? 0);

  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    const list = outgoing.get(e.source) ?? [];
    list.push(e.target);
    outgoing.set(e.source, list);
  }

  const queue = nodes.filter((n) => (indegree.get(n.id) ?? 0) === 0).map((n) => n.id);
  let visited = 0;
  while (queue.length) {
    const id = queue.shift()!;
    visited += 1;
    for (const next of outgoing.get(id) ?? []) {
      indegree.set(next, (indegree.get(next) ?? 1) - 1);
      if ((indegree.get(next) ?? 0) === 0) queue.push(next);
    }
  }
  return visited < nodes.length;
}

/**
 * Would adding an edge from `source` to `target` introduce a directed cycle?
 * True when source === target, or when `target` can already reach `source`
 * (so the new edge would close a loop). Used to reject invalid connections.
 */
export function wouldCreateCycle(
  edges: GraphEdgeLike[],
  source: string,
  target: string,
): boolean {
  if (source === target) return true;
  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    const list = outgoing.get(e.source) ?? [];
    list.push(e.target);
    outgoing.set(e.source, list);
  }
  const stack = [target];
  const seen = new Set<string>();
  while (stack.length) {
    const node = stack.pop()!;
    if (node === source) return true;
    if (seen.has(node)) continue;
    seen.add(node);
    for (const next of outgoing.get(node) ?? []) stack.push(next);
  }
  return false;
}

/**
 * Best-effort output columns of a node given its input columns and config.
 * The mapping mirrors what each transformation does to the schema; it is used
 * only to populate column pickers, so approximations (e.g. join = union) are
 * acceptable.
 */
function outputColumns(
  type: string | undefined,
  config: Record<string, unknown>,
  inputCols: string[],
): string[] {
  switch (type) {
    case "renameColumns": {
      const mapping = (config.mapping ?? {}) as Record<string, string>;
      return inputCols.map((c) => mapping[c] ?? c);
    }
    case "dropColumns": {
      const drop = new Set(asStringArray(config.columns));
      return inputCols.filter((c) => !drop.has(c));
    }
    case "selectColumns": {
      const keep = asStringArray(config.columns);
      return keep.length ? keep.filter((c) => inputCols.includes(c)) : inputCols;
    }
    case "calculatedColumn": {
      const name = typeof config.column_name === "string" ? config.column_name : "";
      return name && !inputCols.includes(name) ? [...inputCols, name] : inputCols;
    }
    case "groupByAggregate": {
      const groupBy = asStringArray(config.group_by);
      const aggs = Object.keys((config.aggregations ?? {}) as Record<string, unknown>);
      const cols = [...groupBy, ...aggs];
      return cols.length ? Array.from(new Set(cols)) : inputCols;
    }
    default:
      // Most cleaning transforms (filter, sort, fill, cast, dedupe, limit,
      // replace, string ops, concat, join) leave the column set unchanged.
      return inputCols;
  }
}

export interface NodeColumns {
  /** Columns available on the wire(s) entering this node. */
  input: string[];
  /** Columns this node emits downstream. */
  output: string[];
}

/**
 * Propagate column schemas forward from input nodes through the whole graph.
 * Input nodes seed their columns from the selected dataset's schema; every
 * other node derives its input columns from the union of its upstream sources.
 */
export function computeNodeColumns(
  nodes: GraphNodeLike[],
  edges: GraphEdgeLike[],
  datasets: Dataset[],
): Map<string, NodeColumns> {
  const datasetById = new Map(datasets.map((d) => [d.id, d]));
  const incoming = incomingByTarget(edges);
  const result = new Map<string, NodeColumns>();

  for (const id of topologicalOrder(nodes, edges)) {
    const node = nodes.find((n) => n.id === id);
    if (!node) continue;

    if (isInputType(node.type)) {
      const datasetId = node.data.config.dataset_id;
      const ds = typeof datasetId === "string" ? datasetById.get(datasetId) : undefined;
      const cols = (ds?.column_schema ?? []).map((f) => f.name);
      result.set(id, { input: [], output: cols });
      continue;
    }

    const sources = incoming.get(id) ?? [];
    const inputSet = new Set<string>();
    for (const { source } of sources) {
      for (const c of result.get(source)?.output ?? []) inputSet.add(c);
    }
    const input = Array.from(inputSet);
    result.set(id, {
      input,
      output: outputColumns(node.type, node.data.config, input),
    });
  }

  return result;
}
