import { describe, expect, it } from "vitest";
import { getNodeSummary } from "../nodeSummary";

describe("getNodeSummary", () => {
  it("returns null for unknown types and unconfigured nodes", () => {
    expect(getNodeSummary("someplugin.customNode", {})).toBeNull();
    expect(getNodeSummary("filterRows", { column: "", operator: "==", value: "" })).toBeNull();
    expect(getNodeSummary("join", { on: "", how: "inner" })).toBeNull();
    expect(getNodeSummary("selectColumns", { columns: [] })).toBeNull();
  });

  it("summarizes input nodes with the dataset name and pinned version", () => {
    expect(
      getNodeSummary("fileInput", { dataset_id: "d1", dataset_version: 3 }, { datasetName: "sales" }),
    ).toBe("sales · v3");
    expect(getNodeSummary("fileInput", { dataset_id: "d1" }, { datasetName: "sales" })).toBe("sales");
    expect(getNodeSummary("fileInput", { dataset_id: "" })).toBeNull();
  });

  it("summarizes SQL and storage nodes", () => {
    expect(getNodeSummary("sqlInput", { mode: "table", table: "orders", schema: "public" })).toBe(
      "public.orders",
    );
    expect(getNodeSummary("sqlInput", { mode: "query", query: "select 1" })).toBe("custom query");
    expect(getNodeSummary("sqlOutput", { table: "out", schema: null })).toBe("→ out");
    expect(getNodeSummary("storageOutput", { path: "bucket/out.parquet", format: "parquet" })).toBe(
      "PARQUET → bucket/out.parquet",
    );
  });

  it("summarizes row filters", () => {
    expect(getNodeSummary("filterRows", { column: "amount", operator: ">", value: "100" })).toBe(
      "amount > 100",
    );
    expect(getNodeSummary("filterRows", { column: "email", operator: "isnull" })).toBe(
      "email is null",
    );
    expect(getNodeSummary("filterExpression", { expression: "amount > 100 and paid" })).toBe(
      "amount > 100 and paid",
    );
  });

  it("summarizes column selections compactly", () => {
    expect(getNodeSummary("selectColumns", { columns: ["a", "b"] })).toBe("a, b");
    expect(getNodeSummary("dropColumns", { columns: ["a", "b", "c", "d"] })).toBe("4 columns");
    expect(getNodeSummary("renameColumns", { mapping: { a: "x", b: "y" } })).toBe("2 renamed");
  });

  it("summarizes joins and aggregations", () => {
    expect(getNodeSummary("join", { on: "id", how: "left" })).toBe("left on id");
    expect(getNodeSummary("join", { on: ["id", "day"], how: "inner" })).toBe("inner on id, day");
    expect(
      getNodeSummary("groupByAggregate", { group_by: ["region"], aggregations: { amount: "sum" } }),
    ).toBe("by region · 1 agg");
  });

  it("summarizes sorting with direction", () => {
    expect(getNodeSummary("sortRows", { columns: ["date"], ascending: false })).toBe("date ↓");
    expect(getNodeSummary("sortRows", { columns: ["date"], ascending: true })).toBe("date ↑");
  });

  it("summarizes quality assertions", () => {
    expect(getNodeSummary("assertNotNull", { columns: ["id"] })).toBe("id");
    expect(getNodeSummary("assertValueRange", { column: "age", min: 0, max: 120 })).toBe(
      "age in [0, 120]",
    );
    expect(getNodeSummary("assertValueRange", { column: "age", min: 0, max: null })).toBe(
      "age in [0, ∞]",
    );
    expect(getNodeSummary("assertRowCount", { min_rows: 10, max_rows: null })).toBe("≥ 10 rows");
    expect(getNodeSummary("assertRowCount", { min_rows: null, max_rows: null })).toBeNull();
  });

  it("summarizes ML nodes", () => {
    expect(getNodeSummary("trainTestSplit", { test_size: 0.2 })).toBe("20% test");
    expect(getNodeSummary("mlCrossValidate", { cv_strategy: "kfold", n_splits: 5 })).toBe(
      "kfold × 5",
    );
    expect(getNodeSummary("mlPredict", { model_uri: "", output_column: "score" })).toBe("→ score");
    // Train nodes surface the chosen algorithm's label (via the ML model map).
    expect(getNodeSummary("mlTrainClassifier", { model_type: "" })).toBeNull();
    expect(getNodeSummary("mlTrainClassifier", { model_type: "random_forest_classifier" })).toBeTruthy();
  });

  it("summarizes chart nodes", () => {
    expect(getNodeSummary("chartBar", { x: "region", y: "amount", aggregate: "sum" })).toBe(
      "sum(amount) by region",
    );
    expect(getNodeSummary("chartBar", { x: "region", aggregate: "count", group_by: "product" })).toBe(
      "count by region / product",
    );
    expect(getNodeSummary("chartBar", {})).toBeNull();
    expect(getNodeSummary("chartLine", { x: "date", y_columns: ["amount"] })).toBe("amount by date");
    expect(getNodeSummary("chartArea", { x: "date", y_columns: ["a", "b", "c"] })).toBe(
      "3 series by date",
    );
    expect(getNodeSummary("chartScatter", { x: "qty", y: "amount" })).toBe("amount vs qty");
    expect(getNodeSummary("chartPie", { category: "region" })).toBe("count by region");
    expect(getNodeSummary("chartHistogram", { column: "amount", bins: 30 })).toBe("amount · 30 bins");
    expect(getNodeSummary("chartBoxPlot", { column: "amount", group_by: "region" })).toBe(
      "amount by region",
    );
    expect(getNodeSummary("chartHeatmap", { columns: [] })).toBe("all numeric columns");
  });

  it("summarizes outputs with format and name", () => {
    expect(getNodeSummary("fileOutput", { format: "parquet", dataset_name: "result" })).toBe(
      "PARQUET → result",
    );
    expect(getNodeSummary("fileOutput", { format: "csv", dataset_name: "" })).toBe("CSV");
  });

  it("clips very long values so the card never overflows", () => {
    const long = "x".repeat(200);
    const summary = getNodeSummary("filterExpression", { expression: long });
    expect(summary).not.toBeNull();
    expect(summary!.length).toBeLessThanOrEqual(46);
    expect(summary!.endsWith("…")).toBe(true);
  });

  it("shows both bounds of a between filter", () => {
    expect(
      getNodeSummary("filterRows", { column: "amount", operator: "between", value: 1, value2: 9 }),
    ).toBe("amount between 1 … 9");
  });

  it("summarizes split-key joins (left_on / right_on)", () => {
    expect(
      getNodeSummary("join", { on: "", how: "left", left_on: ["user_id"], right_on: ["id"] }),
    ).toBe("left on user_id = id");
  });

  it("summarizes fraction-mode sampling", () => {
    expect(getNodeSummary("sampleRows", { frac: 0.1, seed: 42 })).toBe("10% sample");
    expect(getNodeSummary("sampleRows", { n: 100, seed: 42 })).toBe("100 rows");
  });

  it("respects dropNulls how=all semantics", () => {
    expect(getNodeSummary("dropNulls", { subset: [], how: "any" })).toBe("any null value");
    expect(getNodeSummary("dropNulls", { subset: [], how: "all" })).toBe("rows fully null");
    expect(getNodeSummary("dropNulls", { subset: ["a"], how: "all" })).toBe("in a (all null)");
  });

  it("coerces numeric strings from legacy flows", () => {
    expect(getNodeSummary("limitRows", { n: "50", offset: 0 })).toBe("first 50 rows");
    expect(getNodeSummary("trainTestSplit", { test_size: "0.3" })).toBe("30% test");
  });

  it("summarizes misc transforms", () => {
    expect(getNodeSummary("limitRows", { n: 50, offset: 0 })).toBe("first 50 rows");
    expect(getNodeSummary("limitRows", { n: 50, offset: 10 })).toBe("50 rows from 10");
    expect(getNodeSummary("castDtypes", { casts: { a: "int" } })).toBe("1 cast");
    expect(getNodeSummary("stringTransform", { column: "name", operation: "upper" })).toBe(
      "upper(name)",
    );
    expect(getNodeSummary("calculatedColumn", { column_name: "total", expression: "a + b" })).toBe(
      "total = a + b",
    );
    expect(getNodeSummary("dateDifference", { start_column: "start", end_column: "end", unit: "days" })).toBe(
      "end − start (days)",
    );
    expect(getNodeSummary("pythonTransform", { script: "return df" })).toBe("custom script");
  });
});
