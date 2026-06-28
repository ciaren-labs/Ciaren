// Convert backend catalog node specs (GET /api/catalog/nodes) into the editor's
// NodeTypeDef shape and merge them over the static catalog. The static list is
// the seed/offline fallback; the backend (plus installed plugins) is authoritative
// once loaded. Core nodes keep their static ordering; plugin-only nodes are
// appended. Pure functions — no I/O — so they are easy to unit test.

import { type NodeCategory, type NodeTypeDef } from "./nodeCatalog";
import type { CatalogNode, CatalogPort } from "./types";

function toCategory(category: string): NodeCategory {
  // Unknown categories (from a plugin) are kept as-is: the node still resolves
  // and shows in search; it simply won't slot into a known accordion section.
  return category as NodeCategory;
}

function ids(ports: CatalogPort[], predicate: (p: CatalogPort) => boolean): string[] {
  return ports.filter(predicate).map((p) => p.id);
}

/** Convert one backend node spec into the editor's NodeTypeDef. */
export function nodeSpecToDef(spec: CatalogNode): NodeTypeDef {
  const requiredInputs = ids(spec.inputs, (p) => p.required);
  const optionalInputs = ids(spec.inputs, (p) => !p.required);
  const modelInputs = ids(spec.inputs, (p) => p.type === "model");
  const modelOutputs = ids(spec.outputs, (p) => p.type === "model");
  const outputIds = spec.outputs.map((p) => p.id);
  const hasOutput = spec.outputs.length > 0;
  // Match the static convention: a single implicit "out" handle is left
  // undefined; anything else is listed explicitly.
  const isDefaultSingleOut = outputIds.length === 1 && outputIds[0] === "out";

  const def: NodeTypeDef = {
    type: spec.id,
    label: spec.label,
    category: toCategory(spec.category),
    description: spec.description,
    defaultConfig: { ...spec.default_config },
    inputHandles: requiredInputs,
    hasOutput,
    requiresMl: spec.requires_ml,
  };
  if (optionalInputs.length > 0) def.optionalInputHandles = optionalInputs;
  if (modelInputs.length > 0) def.modelInputHandles = modelInputs;
  if (modelOutputs.length > 0) def.modelOutputHandles = modelOutputs;
  if (hasOutput && !isDefaultSingleOut) def.outputHandles = outputIds;
  if (spec.inputs.some((p) => p.multi)) def.multiInput = true;
  if (spec.is_model_sink) def.isModelSink = true;
  return def;
}

/**
 * Merge backend specs over the static defs. Core nodes keep static ordering but
 * take the backend version (backend is authoritative); plugin-only nodes are
 * appended in backend order.
 */
export function mergeNodeCatalog(
  staticDefs: NodeTypeDef[],
  specs: CatalogNode[],
): NodeTypeDef[] {
  const fromBackend = new Map<string, NodeTypeDef>();
  for (const spec of specs) fromBackend.set(spec.id, nodeSpecToDef(spec));

  const merged: NodeTypeDef[] = staticDefs.map(
    (def) => fromBackend.get(def.type) ?? def,
  );

  const staticTypes = new Set(staticDefs.map((d) => d.type));
  for (const spec of specs) {
    if (!staticTypes.has(spec.id)) merged.push(fromBackend.get(spec.id)!);
  }
  return merged;
}
