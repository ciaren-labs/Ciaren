import { describe, expect, it } from "vitest";
import {
  CATEGORY_ORDER,
  NODE_TYPE_MAP,
  getNodeTypeDef,
  getOutputHandles,
} from "../nodeCatalog";
import { computeNodeColumns, type GraphEdgeLike, type GraphNodeLike } from "../flowGraph";
import { validateFlow } from "../flowValidation";
import {
  ML_MODELS,
  getModelDef,
  isSupervisedModel,
  modelsByTask,
} from "../mlModels";
import type { Dataset } from "../types";

const node = (id: string, type: string, config: Record<string, unknown> = {}): GraphNodeLike => ({
  id,
  type,
  data: { config },
});
const edge = (
  source: string,
  target: string,
  targetHandle?: string,
): GraphEdgeLike => ({ source, target, targetHandle: targetHandle ?? null });

function dataset(id: string, cols: string[]): Dataset {
  return {
    id,
    name: id,
    source_type: "csv",
    dataset_kind: "input",
    is_disabled: false,
    project_id: null,
    latest_version: 1,
    version_count: 1,
    column_schema: cols.map((c) => ({ name: c, type: "string" })),
    data_sample: [],
    column_profile: null,
    created_at: "",
    updated_at: "",
  } as Dataset;
}

// ---- Catalog --------------------------------------------------------------

describe("ML node catalog", () => {
  it("registers all nine ML nodes under the 'ml' category", () => {
    const ml = Object.values(NODE_TYPE_MAP).filter((d) => d.category === "ml");
    expect(ml.map((d) => d.type).sort()).toEqual(
      [
        "encodeCategories",
        "featureImportance",
        "mlEvaluate",
        "mlPredict",
        "mlTrain",
        "reduceDimensions",
        "scaleFeatures",
        "selectFeatures",
        "trainTestSplit",
      ].sort(),
    );
    for (const d of ml) expect(d.requiresMl).toBe(true);
  });

  it("orders Machine Learning before Outputs", () => {
    expect(CATEGORY_ORDER.indexOf("ml")).toBeLessThan(CATEGORY_ORDER.indexOf("output"));
  });

  it("declares multi-output handles for split and train", () => {
    expect(getOutputHandles(getNodeTypeDef("trainTestSplit")!)).toEqual(["train", "test"]);
    expect(getOutputHandles(getNodeTypeDef("mlTrain")!)).toEqual(["out", "model"]);
    expect(getOutputHandles(getNodeTypeDef("scaleFeatures")!)).toEqual(["out"]);
  });

  it("marks mlTrain as a model sink and mlPredict's model input optional", () => {
    expect(getNodeTypeDef("mlTrain")!.isModelSink).toBe(true);
    expect(getNodeTypeDef("mlPredict")!.optionalInputHandles).toEqual(["model"]);
  });
});

// ---- Column derivation ----------------------------------------------------

describe("ML column derivation", () => {
  it("mlPredict adds the prediction (and proba) columns", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d" }),
      node("p", "mlPredict", { output_column: "yhat", output_proba_columns: ["p0", "p1"] }),
    ];
    const edges = [edge("in", "p")];
    const cols = computeNodeColumns(nodes, edges, [dataset("d", ["a", "b"])]);
    expect(cols.get("p")!.output).toEqual(["a", "b", "yhat", "p0", "p1"]);
  });

  it("mlEvaluate emits a long-format metric/value frame", () => {
    const nodes = [node("in", "csvInput", { dataset_id: "d" }), node("e", "mlEvaluate", {})];
    const cols = computeNodeColumns(nodes, [edge("in", "e")], [dataset("d", ["a"])]);
    expect(cols.get("e")!.output).toEqual(["metric", "value"]);
  });

  it("featureImportance emits feature_name/importance/rank", () => {
    const nodes = [node("in", "csvInput", { dataset_id: "d" }), node("f", "featureImportance", {})];
    const cols = computeNodeColumns(nodes, [edge("in", "f")], [dataset("d", ["a"])]);
    expect(cols.get("f")!.output).toEqual(["feature_name", "importance", "rank"]);
  });

  it("reduceDimensions replaces chosen columns with components", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d" }),
      node("r", "reduceDimensions", { columns: ["a", "b"], n_components: 2, prefix: "pc" }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "r")], [dataset("d", ["a", "b", "keep"])]);
    expect(cols.get("r")!.output).toEqual(["keep", "pc_1", "pc_2"]);
  });

  it("trainTestSplit passes columns through", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d" }),
      node("s", "trainTestSplit", { seed: 1 }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "s")], [dataset("d", ["a", "b"])]);
    expect(cols.get("s")!.output).toEqual(["a", "b"]);
  });
});

// ---- Validation -----------------------------------------------------------

describe("ML flow validation", () => {
  it("treats a train-only flow (no output node) as valid", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d" }),
      node("tr", "mlTrain", { model_type: "random_forest_classifier", target_column: "y", seed: 1 }),
    ];
    const edges = [edge("in", "tr")];
    const v = validateFlow(nodes, edges, [dataset("d", ["x", "y"])]);
    expect(v.errors.map((e) => e.code)).not.toContain("NO_OUTPUT");
    expect(v.canRun).toBe(true);
  });

  it("flags an mlTrain with no incoming input", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d" }),
      node("tr", "mlTrain", { model_type: "kmeans", seed: 1 }),
      node("out", "csvOutput", { dataset_name: "x" }),
    ];
    // mlTrain not connected to the input
    const edges = [edge("in", "out")];
    const v = validateFlow(nodes, edges, [dataset("d", ["x"])]);
    expect(v.errors.some((e) => e.code === "INPUT_MISSING" && e.nodeId === "tr")).toBe(true);
  });
});

// ---- Model catalog --------------------------------------------------------

describe("ML model catalog", () => {
  it("groups models by task and marks supervised ones", () => {
    const tasks = modelsByTask().map((g) => g.task);
    expect(tasks).toContain("classification");
    expect(tasks).toContain("clustering");
    expect(isSupervisedModel("random_forest_classifier")).toBe(true);
    expect(isSupervisedModel("kmeans")).toBe(false);
  });

  it("every model has a known task and unique value", () => {
    const values = ML_MODELS.map((m) => m.value);
    expect(new Set(values).size).toBe(values.length);
    for (const m of ML_MODELS) expect(getModelDef(m.value)).toBe(m);
  });

  it("xgboost/lightgbm declare their extra requirement", () => {
    expect(getModelDef("xgboost_classifier")!.requires).toBe("xgboost");
    expect(getModelDef("lightgbm_regressor")!.requires).toBe("lightgbm");
  });
});
