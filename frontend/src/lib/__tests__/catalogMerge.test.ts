import { afterEach, describe, expect, it } from "vitest";
import { mergeNodeCatalog, nodeSpecToDef } from "../catalogMerge";
import {
  clearRuntimeNodeDefs,
  getNodeTypeDef,
  isPluginNodeDef,
  NODE_TYPES,
  setRuntimeNodeDefs,
  type NodeTypeDef,
} from "../nodeCatalog";
import type { CatalogNode } from "../types";

function spec(overrides: Partial<CatalogNode> = {}): CatalogNode {
  return {
    id: "x",
    label: "X",
    category: "columns",
    description: "",
    provider: "flowframe.core",
    version: "1.0.0",
    inputs: [{ id: "in", type: "dataframe", required: true, multi: false }],
    outputs: [{ id: "out", type: "dataframe", required: true, multi: false }],
    default_config: {},
    capabilities: [],
    permissions: [],
    requires_ml: false,
    is_model_sink: false,
    config_schema: {},
    ...overrides,
  };
}

afterEach(() => clearRuntimeNodeDefs());

describe("nodeSpecToDef", () => {
  it("maps a simple single-in/single-out node", () => {
    const def = nodeSpecToDef(
      spec({ id: "filterRows", label: "Filter Rows", default_config: { column: "" } }),
    );
    expect(def.type).toBe("filterRows");
    expect(def.label).toBe("Filter Rows");
    expect(def.inputHandles).toEqual(["in"]);
    expect(def.hasOutput).toBe(true);
    expect(def.provider).toBe("flowframe.core");
    // A single implicit "out" is left undefined (static convention).
    expect(def.outputHandles).toBeUndefined();
    expect(def.defaultConfig).toEqual({ column: "" });
  });

  it("maps an input node (no inputs)", () => {
    const def = nodeSpecToDef(spec({ id: "csvInput", category: "input", inputs: [] }));
    expect(def.inputHandles).toEqual([]);
    expect(def.hasOutput).toBe(true);
  });

  it("maps an output node (no outputs)", () => {
    const def = nodeSpecToDef(spec({ id: "csvOutput", category: "output", outputs: [] }));
    expect(def.hasOutput).toBe(false);
    expect(def.outputHandles).toBeUndefined();
  });

  it("maps join's left/right inputs", () => {
    const def = nodeSpecToDef(
      spec({
        id: "join",
        inputs: [
          { id: "left", type: "dataframe", required: true, multi: false },
          { id: "right", type: "dataframe", required: true, multi: false },
        ],
      }),
    );
    expect(def.inputHandles).toEqual(["left", "right"]);
  });

  it("flags a variadic (multi) input", () => {
    const def = nodeSpecToDef(
      spec({ id: "concatRows", inputs: [{ id: "in", type: "dataframe", required: true, multi: true }] }),
    );
    expect(def.multiInput).toBe(true);
  });

  it("maps optional + model input handles (mlPredict)", () => {
    const def = nodeSpecToDef(
      spec({
        id: "mlPredict",
        category: "ml",
        requires_ml: true,
        inputs: [
          { id: "in", type: "dataframe", required: true, multi: false },
          { id: "model", type: "model", required: false, multi: false },
        ],
      }),
    );
    expect(def.inputHandles).toEqual(["in"]);
    expect(def.optionalInputHandles).toEqual(["model"]);
    expect(def.modelInputHandles).toEqual(["model"]);
    expect(def.requiresMl).toBe(true);
  });

  it("maps model output + sink (mlTrain)", () => {
    const def = nodeSpecToDef(
      spec({
        id: "mlTrainClassifier",
        category: "ml",
        is_model_sink: true,
        outputs: [{ id: "model", type: "model", required: true, multi: false }],
      }),
    );
    expect(def.outputHandles).toEqual(["model"]);
    expect(def.modelOutputHandles).toEqual(["model"]);
    expect(def.isModelSink).toBe(true);
  });

  it("lists multi-output handles explicitly (trainTestSplit)", () => {
    const def = nodeSpecToDef(
      spec({
        id: "trainTestSplit",
        outputs: [
          { id: "train", type: "dataframe", required: true, multi: false },
          { id: "test", type: "dataframe", required: true, multi: false },
        ],
      }),
    );
    expect(def.outputHandles).toEqual(["train", "test"]);
  });
});

describe("isPluginNodeDef", () => {
  it("does not treat core or ML providers as plugins", () => {
    const core = nodeSpecToDef(spec({ provider: "flowframe.core" }));
    const ml = nodeSpecToDef(spec({ provider: "flowframe.ml" }));
    const plugin = nodeSpecToDef(spec({ provider: "community.hello" }));

    expect(isPluginNodeDef(core)).toBe(false);
    expect(isPluginNodeDef(ml)).toBe(false);
    expect(isPluginNodeDef(plugin)).toBe(true);
  });
});

describe("mergeNodeCatalog", () => {
  const staticDefs: NodeTypeDef[] = [
    { type: "csvInput", label: "CSV", category: "input", defaultConfig: {}, inputHandles: [], hasOutput: true, description: "static" },
    { type: "filterRows", label: "Filter", category: "clean", defaultConfig: {}, inputHandles: ["in"], hasOutput: true, description: "static" },
  ];

  it("keeps static nodes and preserves order", () => {
    const merged = mergeNodeCatalog(staticDefs, []);
    expect(merged.map((d) => d.type)).toEqual(["csvInput", "filterRows"]);
  });

  it("backend version overrides static for the same type", () => {
    const merged = mergeNodeCatalog(staticDefs, [spec({ id: "filterRows", label: "Filter (backend)", description: "be" })]);
    const filter = merged.find((d) => d.type === "filterRows")!;
    expect(filter.label).toBe("Filter (backend)");
    expect(filter.description).toBe("be");
    // Order unchanged.
    expect(merged.map((d) => d.type)).toEqual(["csvInput", "filterRows"]);
  });

  it("appends plugin-only nodes after the static ones", () => {
    const merged = mergeNodeCatalog(staticDefs, [spec({ id: "hello.greeting", label: "Greeting", provider: "community.hello" })]);
    expect(merged.map((d) => d.type)).toEqual(["csvInput", "filterRows", "hello.greeting"]);
    expect(merged[merged.length - 1]?.provider).toBe("community.hello");
  });
});

describe("runtime overlay", () => {
  it("getNodeTypeDef prefers the overlay then falls back to static", () => {
    expect(getNodeTypeDef("hello.greeting")).toBeUndefined();
    const merged = mergeNodeCatalog(NODE_TYPES, [spec({ id: "hello.greeting", label: "Greeting" })]);
    setRuntimeNodeDefs(merged);
    expect(getNodeTypeDef("hello.greeting")?.label).toBe("Greeting");
    // A core node still resolves.
    expect(getNodeTypeDef("filterRows")?.type).toBe("filterRows");
  });

  it("clearing the overlay restores static-only resolution", () => {
    setRuntimeNodeDefs([{ type: "hello.greeting", label: "G", category: "columns" as never, defaultConfig: {}, inputHandles: ["in"], hasOutput: true, description: "" }]);
    expect(getNodeTypeDef("hello.greeting")).toBeDefined();
    clearRuntimeNodeDefs();
    expect(getNodeTypeDef("hello.greeting")).toBeUndefined();
  });
});
