// Pure graph helpers shared by the editor: topological ordering and
// column-schema propagation. These have no React/xyflow dependencies so they
// can be unit-tested in isolation and reused by the validation layer.

import { getNodeTypeDef, isModelInputHandle } from "./nodeCatalog";
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
  jsonInput: "json",
  textInput: "text",
};

export function isInputType(type: string | undefined): boolean {
  return type ? type in INPUT_SOURCE_TYPE : false;
}

/** All node types that can act as the first node in a flow. */
const FLOW_START_TYPES = new Set([
  ...Object.keys(INPUT_SOURCE_TYPE),
  "sqlInput",
  "storageInput",
]);

/** Connected input types — use connection_id instead of dataset_id. */
const CONNECTED_INPUT_TYPES = new Set(["sqlInput", "storageInput"]);

/** Returns true for any node type that can appear as the first node in a flow. */
export function isFlowStartNode(type: string | undefined): boolean {
  return type ? FLOW_START_TYPES.has(type) : false;
}

/**
 * A flow's first step must be an input node. Returns true once at least one
 * input node is configured (dataset chosen for file inputs, connection chosen
 * for SQL/storage inputs).
 */
export function hasReadyInput(nodes: GraphNodeLike[]): boolean {
  return nodes.some((n) => {
    if (CONNECTED_INPUT_TYPES.has(n.type ?? "")) {
      return (
        typeof n.data.config.connection_id === "string" &&
        n.data.config.connection_id.length > 0
      );
    }
    return (
      isInputType(n.type) &&
      typeof n.data.config.dataset_id === "string" &&
      n.data.config.dataset_id.length > 0
    );
  });
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
    case "binColumn": {
      const name = typeof config.new_column === "string" ? config.new_column : "";
      return name && !inputCols.includes(name) ? [...inputCols, name] : inputCols;
    }
    case "extractDateParts": {
      const col = typeof config.column === "string" ? config.column : "";
      const added = col ? asStringArray(config.parts).map((p) => `${col}_${p}`) : [];
      return Array.from(new Set([...inputCols, ...added]));
    }
    case "unpivot": {
      const idVars = asStringArray(config.id_vars);
      const varName = typeof config.var_name === "string" && config.var_name ? config.var_name : "variable";
      const valueName =
        typeof config.value_name === "string" && config.value_name ? config.value_name : "value";
      return [...idVars, varName, valueName];
    }
    case "pivot": {
      // The pivoted column names are data-dependent; expose the known index cols.
      const index = asStringArray(config.index);
      return index.length ? index : inputCols;
    }
    // ----- ML nodes -----
    case "mlPredict": {
      const out = typeof config.output_column === "string" && config.output_column
        ? config.output_column
        : "prediction";
      const proba = asStringArray(config.output_proba_columns);
      return Array.from(new Set([...inputCols, out, ...proba]));
    }
    case "mlEvaluate":
      return ["metric", "value"];
    case "featureImportance":
      return ["feature_name", "importance", "rank"];
    case "mlTrainClassifier":
    case "mlTrainRegressor":
    case "mlTrainClustering":
    case "mlTrainForecaster":
    case "mlTrainDimReduction":
      // A train node's single output is a model reference, not the training data.
      return ["mlflow_run_id", "model_uri", "task_type"];
    case "reduceDimensions": {
      const cols = asStringArray(config.columns);
      const n = typeof config.n_components === "number" ? config.n_components : 0;
      const prefix = typeof config.prefix === "string" && config.prefix ? config.prefix : "pc";
      if (!cols.length || n < 1) return inputCols; // can't predict without explicit cols
      const kept = inputCols.filter((c) => !cols.includes(c));
      const comps = Array.from({ length: Math.floor(n) }, (_, i) => `${prefix}_${i + 1}`);
      return [...kept, ...comps];
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
 * All node IDs reachable downstream from `sourceId` (not including the source
 * itself). Used to find nodes that may hold stale column references after the
 * source's dataset changes.
 */
export function getDownstreamNodeIds(
  sourceId: string,
  edges: GraphEdgeLike[],
): Set<string> {
  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    const list = outgoing.get(e.source) ?? [];
    list.push(e.target);
    outgoing.set(e.source, list);
  }
  // Seed the source so a cycle that leads back to it doesn't re-visit.
  const seen = new Set<string>([sourceId]);
  const result = new Set<string>();
  const stack = [...(outgoing.get(sourceId) ?? [])];
  while (stack.length) {
    const id = stack.pop()!;
    if (seen.has(id)) continue;
    seen.add(id);
    result.add(id);
    for (const next of outgoing.get(id) ?? []) stack.push(next);
  }
  return result;
}

function filterArr(
  arr: unknown,
  valid: Set<string>,
): { result: string[]; removed: boolean } {
  const src = asStringArray(arr);
  const result = src.filter((c) => valid.has(c));
  return { result, removed: result.length < src.length };
}

/**
 * Remove column references in `config` that are not in `validCols`. Returns
 * the patched config and whether any stale refs were found and cleared. Only
 * fields that are genuine column selectors are touched; free-form expressions
 * and output-column names are left as-is.
 */
export function cleanStaleColumnRefs(
  type: string,
  config: Record<string, unknown>,
  validCols: Set<string>,
): { patched: Record<string, unknown>; hadStale: boolean } {
  let hadStale = false;
  const p = { ...config };

  function arr(key: string) {
    const { result, removed } = filterArr(p[key], validCols);
    if (removed) { p[key] = result; hadStale = true; }
  }
  function single(key: string) {
    const v = p[key];
    if (typeof v === "string" && v && !validCols.has(v)) {
      p[key] = ""; hadStale = true;
    }
  }
  function recKeys(key: string) {
    const obj = p[key];
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return;
    const src = obj as Record<string, unknown>;
    const result = Object.fromEntries(Object.entries(src).filter(([k]) => validCols.has(k)));
    if (Object.keys(result).length < Object.keys(src).length) {
      p[key] = result; hadStale = true;
    }
  }

  switch (type) {
    case "dropNulls":
    case "removeDuplicates":
      arr("subset"); break;
    case "fillNulls":
    case "dropColumns":
    case "selectColumns":
    case "roundNumbers":
    case "removeOutliers":
    case "parseDates":
    case "reduceDimensions":
      arr("columns"); break;
    case "renameColumns":
      recKeys("mapping"); break;
    case "castDtypes":
      recKeys("casts"); break;
    case "filterRows":
    case "replaceValues":
    case "stringTransform":
    case "binColumn":
    case "extractDateParts":
    case "splitColumn":
    case "mapValues":
      single("column"); break;
    case "sortRows":
      arr("columns"); break;
    case "groupByAggregate":
      arr("group_by");
      recKeys("aggregations"); break;
    case "join":
      arr("left_on");
      arr("right_on");
      arr("on"); break;
    case "unpivot":
      arr("id_vars");
      arr("value_vars"); break;
    case "pivot":
      arr("index");
      single("columns");
      single("values"); break;
    case "windowFunction":
      arr("partition_by");
      arr("order_by");
      single("target"); break;
    case "conditionalColumn": {
      const rules = Array.isArray(p.rules) ? (p.rules as Record<string, unknown>[]) : [];
      let rulesChanged = false;
      const cleaned = rules.map((rule) => {
        const conditions = Array.isArray(rule.conditions)
          ? (rule.conditions as Record<string, unknown>[]).map((cond) => {
              if (typeof cond.column === "string" && cond.column && !validCols.has(cond.column)) {
                rulesChanged = true;
                return { ...cond, column: "" };
              }
              return cond;
            })
          : rule.conditions;
        // Legacy flat rule shape: { column, operator, value, result }
        if (typeof rule.column === "string" && rule.column && !validCols.has(rule.column)) {
          rulesChanged = true;
          return { ...rule, conditions, column: "" };
        }
        return Array.isArray(rule.conditions) ? { ...rule, conditions } : rule;
      });
      if (rulesChanged) { p.rules = cleaned; hadStale = true; }
      break;
    }
    case "mlTrainClassifier":
    case "mlTrainRegressor":
    case "mlTrainClustering":
    case "mlTrainForecaster":
    case "mlTrainDimReduction":
      arr("feature_columns");
      single("target_column"); break;
  }

  return { patched: p, hadStale };
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
    const def = getNodeTypeDef(node.type ?? "");
    const inputSet = new Set<string>();
    for (const { source, handle } of sources) {
      // A "model" wire (mlTrain -> mlPredict/featureImportance) carries a trained
      // model, not a dataframe — its columns (mlflow_run_id, model_uri, …) must
      // not pollute the downstream data schema / column pickers.
      if (def && isModelInputHandle(def, handle)) continue;
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
