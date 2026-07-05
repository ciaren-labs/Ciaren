import { describe, expect, it } from "vitest";
import { validateFlow } from "../flowValidation";
import type { GraphEdgeLike, GraphNodeLike } from "../flowGraph";
import type { Dataset } from "../types";

function dataset(
  id: string,
  source: Dataset["source_type"] = "csv",
  latestVersion = 1,
): Dataset {
  return {
    id,
    name: `${id}`,
    source_type: source,
    dataset_kind: "input",
    is_disabled: false,
    project_id: null,
    latest_version: latestVersion,
    version_count: latestVersion,
    column_schema: [{ name: "a", type: "string" }],
    data_sample: [],
    column_profile: null,
    created_at: "",
    updated_at: "",
  };
}

function node(id: string, type: string, config: Record<string, unknown> = {}): GraphNodeLike {
  return { id, type, data: { config } };
}

function edge(source: string, target: string, targetHandle?: string): GraphEdgeLike {
  return { source, target, targetHandle: targetHandle ?? null };
}

const csvDs = dataset("csv1", "csv");
const parquetDs = dataset("pq1", "parquet");

function codes(issues: { code: string }[]): string[] {
  return issues.map((i) => i.code);
}

describe("validateFlow", () => {
  it("flags an empty flow and blocks running", () => {
    const v = validateFlow([], [], []);
    expect(codes(v.errors)).toContain("EMPTY");
    expect(v.canRun).toBe(false);
    expect(v.canPreview).toBe(false);
  });

  it("accepts a valid csv input -> output pipeline", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [csvDs]);
    expect(v.errors).toEqual([]);
    expect(v.canRun).toBe(true);
    expect(v.canExport).toBe(true);
    expect(v.canPreview).toBe(true);
  });

  it("rejects an Excel input node pointed at a Parquet dataset", () => {
    const nodes = [
      node("in", "excelInput", { dataset_id: "pq1" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [parquetDs]);
    expect(codes(v.errors)).toContain("DATASET_TYPE_MISMATCH");
    expect(v.canRun).toBe(false);
  });

  it("validates File Input against the exact selected extension", () => {
    const jsonDs = dataset("json1", "json");
    const jsonlDs = dataset("jsonl1", "jsonl");
    const nodes = [
      node("in", "fileInput", { dataset_id: "json1", format: "jsonl" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];

    const mismatch = validateFlow(nodes, [edge("in", "out")], [jsonDs, jsonlDs]);
    expect(codes(mismatch.errors)).toContain("DATASET_TYPE_MISMATCH");

    const valid = validateFlow(
      [node("in", "fileInput", { dataset_id: "jsonl1", format: "jsonl" }), nodes[1]],
      [edge("in", "out")],
      [jsonDs, jsonlDs],
    );
    expect(valid.errors).toEqual([]);
  });

  it("errors when an input pins a version beyond the latest", () => {
    const ds = dataset("csv1", "csv", 2); // latest = v2
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1", dataset_version: 5 }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [ds]);
    expect(codes(v.errors)).toContain("VERSION_MISSING");
    expect(v.canRun).toBe(false);
  });

  it("warns (but allows running) when an input pins an outdated version", () => {
    const ds = dataset("csv1", "csv", 3); // latest = v3
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1", dataset_version: 1 }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [ds]);
    expect(v.warnings.map((w) => w.code)).toContain("VERSION_OUTDATED");
    expect(v.canRun).toBe(true);
  });

  it("accepts an input pinned to the latest version", () => {
    const ds = dataset("csv1", "csv", 2);
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1", dataset_version: 2 }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [ds]);
    expect(v.errors).toEqual([]);
    expect(v.warnings).toEqual([]);
  });

  it("flags a missing dataset reference", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "gone" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [csvDs]);
    expect(codes(v.errors)).toContain("DATASET_MISSING");
  });

  it("requires an output node to run but still allows preview", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("drop", "dropColumns", { columns: ["a"] }),
    ];
    const v = validateFlow(nodes, [edge("in", "drop")], [csvDs]);
    expect(codes(v.errors)).toContain("NO_OUTPUT");
    expect(v.canRun).toBe(false);
    expect(v.canPreview).toBe(true);
  });

  it("flags an unconnected single input", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("drop", "dropColumns", { columns: ["a"] }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    // drop has no incoming edge.
    const v = validateFlow(nodes, [edge("drop", "out")], [csvDs]);
    expect(codes(v.errors)).toContain("INPUT_MISSING");
  });

  it("requires both sides of a join", () => {
    const nodes = [
      node("l", "csvInput", { dataset_id: "csv1" }),
      node("j", "join", { on: "a", how: "inner" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("l", "j", "left"), edge("j", "out")], [csvDs]);
    const inputMissing = v.errors.filter((e) => e.code === "INPUT_MISSING");
    expect(inputMissing.length).toBeGreaterThan(0);
  });

  it("detects a cycle", () => {
    const nodes = [
      node("a", "dropColumns", { columns: ["a"] }),
      node("b", "dropColumns", { columns: ["a"] }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges = [edge("a", "b"), edge("b", "a"), edge("b", "out")];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("CYCLE");
  });

  it("flags mlPredict with no model wire and no model URI", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("p", "mlPredict", { output_column: "prediction" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "p"), edge("p", "out")], [csvDs]);
    expect(codes(v.errors)).toContain("MODEL_MISSING");
    expect(v.canRun).toBe(false);
  });

  it("accepts mlPredict when a model URI is provided", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("p", "mlPredict", { output_column: "prediction", model_uri: "models:/churn@production" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "p"), edge("p", "out")], [csvDs]);
    expect(codes(v.errors)).not.toContain("MODEL_MISSING");
  });

  it("accepts mlPredict when a model is wired to the model input", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("t", "mlTrainClassifier", { model_type: "logistic_regression", target_column: "a", feature_columns: ["a"] }),
      node("p", "mlPredict", { output_column: "prediction" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges = [
      edge("in", "t"),
      edge("t", "p", "model"),
      edge("in", "p"),
      edge("p", "out"),
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).not.toContain("MODEL_MISSING");
  });

  it("rejects Train -> Cross-Validate to avoid duplicate full-data training", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("t", "mlTrainClassifier", { model_type: "logistic_regression", target_column: "a" }),
      node("cv", "mlCrossValidate", { cv_strategy: "kfold", n_splits: 3, seed: 1 }),
    ];
    const edges = [edge("in", "t"), edge("in", "cv"), edge("t", "cv", "model")];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("MODEL_SOURCE_MISMATCH");
  });

  it("accepts Model Definition -> Cross-Validate", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("m", "mlClassifierModel", { model_type: "logistic_regression", target_column: "a", seed: 1 }),
      node("cv", "mlCrossValidate", { cv_strategy: "kfold", n_splits: 3, seed: 1 }),
    ];
    const edges = [edge("in", "m"), edge("in", "cv"), edge("m", "cv", "model")];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).not.toContain("MODEL_SOURCE_MISMATCH");
  });

  // The canvas blocks these connections interactively; these cases cover
  // graphs that arrive with edges already in place (imported / hand-edited).
  it("flags a model output wired into a data input", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("t", "mlTrainClassifier", {
        model_type: "logistic_regression",
        target_column: "a",
        feature_columns: ["a"],
      }),
      node("clean", "dropNulls", { subset: [], how: "any" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      edge("in", "t"),
      // A train node's only output is its model wire — even without an
      // explicit sourceHandle it must not feed a data input.
      { source: "t", target: "clean", sourceHandle: null, targetHandle: null },
      edge("clean", "out"),
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("MODEL_WIRE_MISMATCH");
    expect(v.canRun).toBe(false);
  });

  it("flags a dataframe wired into a model input", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("p", "mlPredict", { output_column: "prediction", model_uri: "models:/m@prod" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      edge("in", "p"),
      { source: "in", target: "p", sourceHandle: "out", targetHandle: "model" },
      edge("p", "out"),
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("MODEL_WIRE_MISMATCH");
  });

  it("accepts a proper model wire without a mismatch error", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("t", "mlTrainClassifier", {
        model_type: "logistic_regression",
        target_column: "a",
        feature_columns: ["a"],
      }),
      node("p", "mlPredict", { output_column: "prediction" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      edge("in", "t"),
      edge("t", "p", "model"),
      edge("in", "p"),
      edge("p", "out"),
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).not.toContain("MODEL_WIRE_MISMATCH");
  });

  it("flags two edges into a single-input handle (imported graphs)", () => {
    const nodes = [
      node("in1", "csvInput", { dataset_id: "csv1" }),
      node("in2", "csvInput", { dataset_id: "csv1" }),
      node("clean", "dropNulls", { subset: [], how: "any" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      // One edge with a null handle, one explicit — both resolve to "in".
      { source: "in1", target: "clean", sourceHandle: null, targetHandle: null },
      { source: "in2", target: "clean", sourceHandle: null, targetHandle: "in" },
      edge("clean", "out"),
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("INPUT_CONFLICT");
    expect(v.canRun).toBe(false);
  });

  it("allows many edges into a multi-input node without conflict", () => {
    const nodes = [
      node("in1", "csvInput", { dataset_id: "csv1" }),
      node("in2", "csvInput", { dataset_id: "csv1" }),
      node("stack", "concatRows", {}),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges = [edge("in1", "stack"), edge("in2", "stack"), edge("stack", "out")];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).not.toContain("INPUT_CONFLICT");
  });

  it("flags an ambiguous edge leaving a multi-output node", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("split", "trainTestSplit", { test_size: 0.2, stratify_column: null, seed: 42 }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      edge("in", "split"),
      // Which output — train or test? The backend refuses this; so do we.
      { source: "split", target: "out", sourceHandle: null, targetHandle: null },
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("SOURCE_HANDLE_INVALID");

    const ok = validateFlow(
      nodes,
      [edge("in", "split"), { source: "split", target: "out", sourceHandle: "train", targetHandle: null }],
      [csvDs],
    );
    expect(codes(ok.errors)).not.toContain("SOURCE_HANDLE_INVALID");
  });

  it("flags an edge leaving an undeclared output handle", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "csv1" }),
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const edges: GraphEdgeLike[] = [
      { source: "in", target: "out", sourceHandle: "bogus", targetHandle: null },
    ];
    const v = validateFlow(nodes, edges, [csvDs]);
    expect(codes(v.errors)).toContain("SOURCE_HANDLE_INVALID");
  });

  it("flags invalid node config", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "" }), // empty -> zod error
      node("out", "csvOutput", { dataset_name: "output" }),
    ];
    const v = validateFlow(nodes, [edge("in", "out")], [csvDs]);
    expect(codes(v.errors)).toContain("CONFIG_INVALID");
  });

  it("groups errors by node id", () => {
    const nodes = [node("in", "csvInput", { dataset_id: "" })];
    const v = validateFlow(nodes, [], [csvDs]);
    expect(v.errorsByNode.get("in")?.length).toBeGreaterThan(0);
  });
});
