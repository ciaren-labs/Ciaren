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
