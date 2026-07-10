// Contract: the static node catalog fallback (NODE_TYPES in nodeCatalog.ts) must
// agree with what the backend serves for every built-in (ciaren.core) node. The
// backend is the source of truth; this fallback only powers offline/first-paint, so
// if it drifts (a relabelled node, a changed default, a different handle topology)
// the palette and edge-validation silently differ from a real backend session.
//
// The fixture backendNodeCatalog.snapshot.json is generated + guarded by the backend
// (backend/tests/test_node_catalog_contract.py). If this test fails, reconcile
// nodeCatalog.ts with the backend change (or regenerate the fixture if the backend
// metadata legitimately changed).

import { describe, expect, it } from "vitest";
import { nodeSpecToDef } from "@/lib/catalogMerge";
import { NODE_TYPE_MAP, type NodeTypeDef } from "../nodeCatalog";
import type { CatalogNode } from "@/features/flows/types";
import backendSpecs from "./backendNodeCatalog.snapshot.json";

const specs = backendSpecs as unknown as CatalogNode[];

// The fields the backend owns and that must match the static fallback exactly. We
// deliberately exclude frontend-only concerns: `hidden` (palette visibility set only
// on the client), `provider`/`description`/`configSchema` (not correctness-critical
// for the fallback's palette + edge behavior).
function comparable(def: NodeTypeDef) {
  return {
    type: def.type,
    label: def.label,
    category: def.category,
    defaultConfig: def.defaultConfig,
    inputHandles: def.inputHandles ?? [],
    optionalInputHandles: def.optionalInputHandles ?? [],
    outputHandles: def.outputHandles ?? [],
    modelInputHandles: def.modelInputHandles ?? [],
    modelOutputHandles: def.modelOutputHandles ?? [],
    hasOutput: def.hasOutput,
    multiInput: def.multiInput ?? false,
    requiresMl: def.requiresMl ?? false,
    isModelSink: def.isModelSink ?? false,
    isFlowTerminal: def.isFlowTerminal ?? false,
  };
}

describe("node catalog contract (static fallback vs backend)", () => {
  it("has a static def for every core backend node", () => {
    const missing = specs.filter((s) => !NODE_TYPE_MAP[s.id]).map((s) => s.id);
    expect(missing).toEqual([]);
  });

  it.each(specs.map((s) => [s.id, s] as const))(
    "static def for %s matches the backend",
    (id, spec) => {
      const staticDef = NODE_TYPE_MAP[id];
      expect(staticDef, `no static def for ${id}`).toBeDefined();
      expect(comparable(staticDef)).toEqual(comparable(nodeSpecToDef(spec)));
    },
  );
});
