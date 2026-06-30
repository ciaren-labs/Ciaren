import { describe, expect, it } from "vitest";
import {
  cleanStaleColumnRefs,
  computeNodeColumns,
  getDownstreamNodeIds,
  hasCycle,
  hasReadyInput,
  isInputType,
  topologicalOrder,
  wouldCreateCycle,
  type GraphEdgeLike,
  type GraphNodeLike,
} from "../flowGraph";
import type { Dataset } from "../types";

function dataset(id: string, cols: string[], source: Dataset["source_type"] = "csv"): Dataset {
  return {
    id,
    name: `${id}.csv`,
    source_type: source,
    dataset_kind: "input",
    is_disabled: false,
    project_id: null,
    latest_version: 1,
    version_count: 1,
    column_schema: cols.map((name) => ({ name, type: "string" })),
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

describe("isInputType", () => {
  it("recognises input node types", () => {
    expect(isInputType("fileInput")).toBe(true);
    expect(isInputType("csvInput")).toBe(true);
    expect(isInputType("excelInput")).toBe(true);
    expect(isInputType("dropColumns")).toBe(false);
    expect(isInputType(undefined)).toBe(false);
  });
});

describe("hasReadyInput", () => {
  it("is false with no nodes", () => {
    expect(hasReadyInput([])).toBe(false);
  });

  it("is false when an input node has no dataset chosen", () => {
    expect(hasReadyInput([node("in", "csvInput", { dataset_id: "" })])).toBe(false);
  });

  it("is false when only non-input nodes exist", () => {
    expect(hasReadyInput([node("d", "dropColumns", { columns: [] })])).toBe(false);
  });

  it("is true once an input node has a dataset", () => {
    expect(hasReadyInput([node("in", "csvInput", { dataset_id: "d1" })])).toBe(true);
  });

  it("is true once a File Input node has a dataset", () => {
    expect(hasReadyInput([node("in", "fileInput", { dataset_id: "d1", format: "csv" })])).toBe(true);
  });
});

describe("topologicalOrder", () => {
  it("orders sources before targets", () => {
    const nodes = [node("a", "csvInput"), node("b", "dropColumns"), node("c", "csvOutput")];
    const edges = [edge("a", "b"), edge("b", "c")];
    const order = topologicalOrder(nodes, edges);
    expect(order.indexOf("a")).toBeLessThan(order.indexOf("b"));
    expect(order.indexOf("b")).toBeLessThan(order.indexOf("c"));
  });

  it("still returns every node when a cycle exists", () => {
    const nodes = [node("a", "dropColumns"), node("b", "dropColumns")];
    const edges = [edge("a", "b"), edge("b", "a")];
    expect(topologicalOrder(nodes, edges).sort()).toEqual(["a", "b"]);
  });
});

describe("hasCycle", () => {
  it("is false for a linear pipeline", () => {
    const nodes = [node("a", "csvInput"), node("b", "csvOutput")];
    expect(hasCycle(nodes, [edge("a", "b")])).toBe(false);
  });

  it("is true when nodes form a loop", () => {
    const nodes = [node("a", "dropColumns"), node("b", "dropColumns")];
    expect(hasCycle(nodes, [edge("a", "b"), edge("b", "a")])).toBe(true);
  });
});

describe("wouldCreateCycle", () => {
  it("rejects a self-loop", () => {
    expect(wouldCreateCycle([], "a", "a")).toBe(true);
  });

  it("rejects an edge that closes a loop", () => {
    // a -> b already exists; adding b -> a would cycle.
    expect(wouldCreateCycle([edge("a", "b")], "b", "a")).toBe(true);
  });

  it("allows a forward edge", () => {
    expect(wouldCreateCycle([edge("a", "b")], "b", "c")).toBe(false);
  });

  it("allows fan-out from one source to multiple targets", () => {
    const edges = [edge("a", "b")];
    expect(wouldCreateCycle(edges, "a", "c")).toBe(false);
  });
});

describe("computeNodeColumns", () => {
  const datasets = [dataset("d1", ["name", "age", "score"])];

  it("seeds input nodes from the dataset schema", () => {
    const nodes = [node("in", "csvInput", { dataset_id: "d1" })];
    const cols = computeNodeColumns(nodes, [], datasets);
    expect(cols.get("in")?.output).toEqual(["name", "age", "score"]);
  });

  it("propagates columns and applies dropColumns", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("drop", "dropColumns", { columns: ["age"] }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "drop")], datasets);
    expect(cols.get("drop")?.input).toEqual(["name", "age", "score"]);
    expect(cols.get("drop")?.output).toEqual(["name", "score"]);
  });

  it("applies selectColumns and renameColumns", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("sel", "selectColumns", { columns: ["name", "age"] }),
      node("ren", "renameColumns", { mapping: { name: "full_name" } }),
    ];
    const edges = [edge("in", "sel"), edge("sel", "ren")];
    const cols = computeNodeColumns(nodes, edges, datasets);
    expect(cols.get("sel")?.output).toEqual(["name", "age"]);
    expect(cols.get("ren")?.output).toEqual(["full_name", "age"]);
  });

  it("adds the calculated column to the output schema", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("calc", "calculatedColumn", { column_name: "total", expression: "age * 2" }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "calc")], datasets);
    expect(cols.get("calc")?.output).toContain("total");
  });

  it("adds the bin column to the output schema", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("bin", "binColumn", { column: "age", new_column: "age_bucket", bins: 3 }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "bin")], datasets);
    expect(cols.get("bin")?.output).toContain("age_bucket");
  });

  it("adds extracted date-part columns", () => {
    const ds = [dataset("d1", ["when"])];
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("ex", "extractDateParts", { column: "when", parts: ["year", "month"] }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "ex")], ds);
    expect(cols.get("ex")?.output).toEqual(["when", "when_year", "when_month"]);
  });

  it("reshapes columns for unpivot", () => {
    const ds = [dataset("d1", ["id", "jan", "feb"])];
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("u", "unpivot", { id_vars: ["id"], var_name: "month", value_name: "amount" }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "u")], ds);
    expect(cols.get("u")?.output).toEqual(["id", "month", "amount"]);
  });

  it("unions the two sides of a join", () => {
    const ds = [dataset("d1", ["id", "name"]), dataset("d2", ["id", "amount"])];
    const nodes = [
      node("l", "csvInput", { dataset_id: "d1" }),
      node("r", "csvInput", { dataset_id: "d2" }),
      node("j", "join", { on: "id", how: "inner" }),
    ];
    const edges = [edge("l", "j", "left"), edge("r", "j", "right")];
    const cols = computeNodeColumns(nodes, edges, ds);
    expect(cols.get("j")?.input.sort()).toEqual(["amount", "id", "name"]);
  });

  it("does not let a model wire pollute mlPredict's data columns", () => {
    // mlTrain's output frame is a model reference (mlflow_run_id, model_uri,
    // task_type). Wired into mlPredict's "model" input it must NOT contribute
    // those columns to the data schema — only the data "in" wire does.
    const ds = [dataset("d1", ["x1", "x2", "target"])];
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("tr", "mlTrainClassifier", { model_type: "random_forest_classifier", target_column: "target" }),
      node("pr", "mlPredict", { output_column: "prediction" }),
    ];
    const edges = [
      edge("in", "tr"), // data -> train
      edge("in", "pr"), // data -> predict.in
      edge("tr", "pr", "model"), // model -> predict.model
    ];
    const cols = computeNodeColumns(nodes, edges, ds);
    // Input is the data columns only — no model-reference columns.
    expect(cols.get("pr")?.input.sort()).toEqual(["target", "x1", "x2"]);
    expect(cols.get("pr")?.output).not.toContain("model_uri");
    expect(cols.get("pr")?.output).not.toContain("mlflow_run_id");
    expect(cols.get("pr")?.output).toContain("prediction");
  });

  it("gives featureImportance no data columns from its model wire", () => {
    const ds = [dataset("d1", ["x1", "x2", "target"])];
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("tr", "mlTrainClassifier", { model_type: "random_forest_classifier", target_column: "target" }),
      node("fi", "featureImportance", {}),
    ];
    const edges = [edge("in", "tr"), edge("tr", "fi", "model")];
    const cols = computeNodeColumns(nodes, edges, ds);
    expect(cols.get("fi")?.input).toEqual([]); // model wire carries no data columns
    expect(cols.get("fi")?.output).toEqual(["feature_name", "importance", "rank"]);
  });
});

// ---------------------------------------------------------------------------
// getDownstreamNodeIds
// ---------------------------------------------------------------------------

describe("getDownstreamNodeIds", () => {
  it("returns empty set when source has no outgoing edges", () => {
    const result = getDownstreamNodeIds("a", []);
    expect(result.size).toBe(0);
  });

  it("returns the direct successor", () => {
    const result = getDownstreamNodeIds("a", [edge("a", "b")]);
    expect(result).toEqual(new Set(["b"]));
  });

  it("traverses multiple hops", () => {
    const edges = [edge("a", "b"), edge("b", "c"), edge("c", "d")];
    const result = getDownstreamNodeIds("a", edges);
    expect(result).toEqual(new Set(["b", "c", "d"]));
  });

  it("includes all branches in a fan-out graph", () => {
    // a -> b, a -> c, b -> d
    const edges = [edge("a", "b"), edge("a", "c"), edge("b", "d")];
    const result = getDownstreamNodeIds("a", edges);
    expect(result).toEqual(new Set(["b", "c", "d"]));
  });

  it("deduplicates diamond-shaped paths", () => {
    // a -> b, a -> c, b -> d, c -> d  (d reachable via two routes)
    const edges = [edge("a", "b"), edge("a", "c"), edge("b", "d"), edge("c", "d")];
    const result = getDownstreamNodeIds("a", edges);
    expect(result).toEqual(new Set(["b", "c", "d"]));
  });

  it("does not include the source node itself", () => {
    const result = getDownstreamNodeIds("a", [edge("a", "b"), edge("b", "a")]);
    expect(result.has("a")).toBe(false);
  });

  it("does not include nodes that are upstream only", () => {
    // x -> a -> b;  x is upstream of a, not downstream
    const edges = [edge("x", "a"), edge("a", "b")];
    const result = getDownstreamNodeIds("a", edges);
    expect(result.has("x")).toBe(false);
    expect(result.has("b")).toBe(true);
  });

  it("returns empty set when the source is the last node", () => {
    const result = getDownstreamNodeIds("b", [edge("a", "b")]);
    expect(result.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// cleanStaleColumnRefs — helpers
// ---------------------------------------------------------------------------

const VALID = new Set(["name", "age", "score"]);

/** Shorthand: clean config of `type` and assert no stale refs were found. */
function expectClean(type: string, config: Record<string, unknown>) {
  const { hadStale, patched } = cleanStaleColumnRefs(type, config, VALID);
  expect(hadStale).toBe(false);
  expect(patched).toEqual(config);
}

/** Shorthand: clean config of `type` and return the patched config. */
function clean(type: string, config: Record<string, unknown>) {
  return cleanStaleColumnRefs(type, config, VALID);
}

describe("cleanStaleColumnRefs — no-op cases", () => {
  it("returns hadStale=false when all column refs are valid", () => {
    expectClean("dropColumns", { columns: ["name", "age"] });
    expectClean("selectColumns", { columns: ["score"] });
    expectClean("filterRows", { column: "age", operator: "==", value: "42" });
    expectClean("sortRows", { columns: ["name", "score"] });
    expectClean("renameColumns", { mapping: { name: "full_name", age: "years" } });
    expectClean("groupByAggregate", { group_by: ["name"], aggregations: { age: "mean" } });
  });

  it("returns hadStale=false for empty arrays", () => {
    expectClean("dropColumns", { columns: [] });
    expectClean("dropNulls", { subset: [] });
    expectClean("groupByAggregate", { group_by: [], aggregations: {} });
  });

  it("returns hadStale=false for optional fields that are absent", () => {
    expectClean("dropNulls", { how: "any" }); // no subset key
    expectClean("fillNulls", { strategy: "constant", value: "0" }); // no columns key
    expectClean("windowFunction", { function: "row_number", new_column: "rn" }); // no partition_by/order_by/target
  });

  it("returns hadStale=false for unknown node types (no-op)", () => {
    expectClean("csvOutput", { path: "out.csv" });
    expectClean("concatRows", {});
    expectClean("limitRows", { n: 10 });
  });

  it("does not mutate the original config object", () => {
    const config = { columns: ["name", "unknown_col"] };
    clean("dropColumns", config);
    expect(config.columns).toEqual(["name", "unknown_col"]); // original unchanged
  });
});

describe("cleanStaleColumnRefs — array fields", () => {
  it("removes stale entries from dropColumns.columns", () => {
    const { hadStale, patched } = clean("dropColumns", { columns: ["name", "missing", "age"] });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["name", "age"]);
  });

  it("removes stale entries from selectColumns.columns", () => {
    const { hadStale, patched } = clean("selectColumns", { columns: ["gone", "score"] });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["score"]);
  });

  it("removes all entries when none are valid (dropColumns)", () => {
    const { hadStale, patched } = clean("dropColumns", { columns: ["x", "y", "z"] });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual([]);
  });

  it("clears subset for dropNulls", () => {
    const { hadStale, patched } = clean("dropNulls", { subset: ["age", "gone"], how: "any" });
    expect(hadStale).toBe(true);
    expect(patched.subset).toEqual(["age"]);
    expect(patched.how).toBe("any"); // non-column field preserved
  });

  it("clears subset for removeDuplicates", () => {
    const { hadStale, patched } = clean("removeDuplicates", { subset: ["gone"], keep: "first" });
    expect(hadStale).toBe(true);
    expect(patched.subset).toEqual([]);
  });

  it("clears columns for fillNulls", () => {
    const { hadStale, patched } = clean("fillNulls", { strategy: "mean", columns: ["age", "missing"] });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["age"]);
  });

  it("clears columns for sortRows (multi-column sort)", () => {
    const { hadStale, patched } = clean("sortRows", { columns: ["name", "gone"], ascending: true });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["name"]);
  });

  it("clears columns for roundNumbers", () => {
    const { hadStale, patched } = clean("roundNumbers", { columns: ["age", "bad_col"], decimals: 2 });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["age"]);
  });

  it("clears columns for removeOutliers", () => {
    const { hadStale, patched } = clean("removeOutliers", { columns: ["score", "nonexistent"], method: "iqr" });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["score"]);
  });

  it("clears columns for parseDates", () => {
    const { hadStale, patched } = clean("parseDates", { columns: ["missing_date"] });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual([]);
  });

  it("clears columns for reduceDimensions", () => {
    const { hadStale, patched } = clean("reduceDimensions", { columns: ["age", "gone"], n_components: 2 });
    expect(hadStale).toBe(true);
    expect(patched.columns).toEqual(["age"]);
  });
});

describe("cleanStaleColumnRefs — single column fields", () => {
  it("clears filterRows.column when invalid", () => {
    const { hadStale, patched } = clean("filterRows", { column: "deleted_col", operator: ">", value: "0" });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
    expect(patched.operator).toBe(">"); // non-column fields preserved
  });

  it("leaves filterRows.column when valid", () => {
    expectClean("filterRows", { column: "age", operator: ">", value: "0" });
  });

  it("clears replaceValues.column when invalid", () => {
    const { hadStale, patched } = clean("replaceValues", { column: "gone", to_replace: "x", value: "y" });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
  });

  it("clears stringTransform.column when invalid", () => {
    const { hadStale, patched } = clean("stringTransform", { column: "removed", operation: "lower" });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
  });

  it("clears binColumn.column when invalid", () => {
    const { hadStale, patched } = clean("binColumn", { column: "stale", new_column: "stale_bin", bins: 4 });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
    expect(patched.new_column).toBe("stale_bin"); // output name preserved
  });

  it("clears extractDateParts.column when invalid", () => {
    const { hadStale, patched } = clean("extractDateParts", { column: "old_date", parts: ["year"] });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
  });

  it("clears splitColumn.column when invalid", () => {
    const { hadStale, patched } = clean("splitColumn", { column: "gone", mode: "delimiter", delimiter: "," });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
  });

  it("clears mapValues.column when invalid", () => {
    const { hadStale, patched } = clean("mapValues", { column: "missing", mapping: { a: "b" } });
    expect(hadStale).toBe(true);
    expect(patched.column).toBe("");
  });

  it("ignores column when value is empty string (already unset)", () => {
    expectClean("filterRows", { column: "", operator: "==", value: "" });
  });
});

describe("cleanStaleColumnRefs — record-key fields", () => {
  it("removes stale keys from renameColumns.mapping", () => {
    const { hadStale, patched } = clean("renameColumns", {
      mapping: { name: "full_name", gone: "new_gone", age: "years" },
    });
    expect(hadStale).toBe(true);
    expect(patched.mapping).toEqual({ name: "full_name", age: "years" });
  });

  it("removes all keys when none are valid (renameColumns)", () => {
    const { hadStale, patched } = clean("renameColumns", { mapping: { x: "a", y: "b" } });
    expect(hadStale).toBe(true);
    expect(patched.mapping).toEqual({});
  });

  it("removes stale keys from castDtypes.casts", () => {
    const { hadStale, patched } = clean("castDtypes", {
      casts: { age: "integer", gone: "string", score: "float" },
    });
    expect(hadStale).toBe(true);
    expect(patched.casts).toEqual({ age: "integer", score: "float" });
  });

  it("removes stale keys from groupByAggregate.aggregations", () => {
    const { hadStale, patched } = clean("groupByAggregate", {
      group_by: ["name"],
      aggregations: { age: "mean", missing: "sum", score: "max" },
    });
    expect(hadStale).toBe(true);
    expect(patched.group_by).toEqual(["name"]);
    expect(patched.aggregations).toEqual({ age: "mean", score: "max" });
  });

  it("handles missing or non-object mapping gracefully", () => {
    expectClean("renameColumns", { mapping: null });
    expectClean("renameColumns", { mapping: undefined });
    expectClean("castDtypes", { casts: [] }); // array is not a record
  });
});

describe("cleanStaleColumnRefs — join node", () => {
  it("clears invalid columns from on (shared-key join)", () => {
    const { hadStale, patched } = clean("join", { on: ["name", "gone"], how: "inner" });
    expect(hadStale).toBe(true);
    expect(patched.on).toEqual(["name"]);
  });

  it("clears invalid columns from left_on and right_on (split-key join)", () => {
    const { hadStale, patched } = clean("join", {
      left_on: ["name", "bad"],
      right_on: ["score", "also_bad"],
      how: "left",
    });
    expect(hadStale).toBe(true);
    expect(patched.left_on).toEqual(["name"]);
    expect(patched.right_on).toEqual(["score"]);
  });

  it("no-op when all join keys are valid", () => {
    expectClean("join", { on: ["name", "age"], how: "inner" });
  });
});

describe("cleanStaleColumnRefs — pivot / unpivot", () => {
  it("clears stale index columns from pivot", () => {
    const { hadStale, patched } = clean("pivot", {
      index: ["name", "gone"],
      columns: "age",
      values: "score",
      aggfunc: "sum",
    });
    expect(hadStale).toBe(true);
    expect(patched.index).toEqual(["name"]);
    expect(patched.columns).toBe("age"); // valid, preserved
    expect(patched.values).toBe("score"); // valid, preserved
  });

  it("clears stale pivot.columns (the pivot column) when invalid", () => {
    const { hadStale, patched } = clean("pivot", {
      index: ["name"],
      columns: "deleted_col",
      values: "score",
    });
    expect(hadStale).toBe(true);
    expect(patched.columns).toBe("");
  });

  it("clears stale pivot.values when invalid", () => {
    const { hadStale, patched } = clean("pivot", {
      index: ["name"],
      columns: "age",
      values: "gone",
    });
    expect(hadStale).toBe(true);
    expect(patched.values).toBe("");
  });

  it("clears stale columns from unpivot.id_vars and value_vars", () => {
    const { hadStale, patched } = clean("unpivot", {
      id_vars: ["name", "removed"],
      value_vars: ["age", "also_gone"],
      var_name: "metric",
      value_name: "val",
    });
    expect(hadStale).toBe(true);
    expect(patched.id_vars).toEqual(["name"]);
    expect(patched.value_vars).toEqual(["age"]);
    expect(patched.var_name).toBe("metric"); // non-column preserved
  });
});

describe("cleanStaleColumnRefs — windowFunction", () => {
  it("clears stale partition_by and order_by columns", () => {
    const { hadStale, patched } = clean("windowFunction", {
      function: "rank",
      new_column: "rnk",
      partition_by: ["name", "gone"],
      order_by: ["score", "missing"],
    });
    expect(hadStale).toBe(true);
    expect(patched.partition_by).toEqual(["name"]);
    expect(patched.order_by).toEqual(["score"]);
  });

  it("clears stale target column for value functions", () => {
    const { hadStale, patched } = clean("windowFunction", {
      function: "cumsum",
      new_column: "running_total",
      partition_by: [],
      order_by: ["name"],
      target: "deleted_value",
    });
    expect(hadStale).toBe(true);
    expect(patched.target).toBe("");
  });

  it("preserves valid target column", () => {
    expectClean("windowFunction", {
      function: "cumsum",
      new_column: "running",
      order_by: ["name"],
      target: "age",
    });
  });
});

describe("cleanStaleColumnRefs — conditionalColumn", () => {
  it("clears stale column in new-shape rules", () => {
    const { hadStale, patched } = clean("conditionalColumn", {
      rules: [
        { match: "all", conditions: [{ column: "name", operator: "==", value: "Alice" }], result: "yes" },
        { match: "all", conditions: [{ column: "gone", operator: ">", value: "0" }], result: "no" },
      ],
      new_column: "flag",
    });
    expect(hadStale).toBe(true);
    const rules = patched.rules as any[];
    expect(rules[0].conditions[0].column).toBe("name"); // valid, kept
    expect(rules[1].conditions[0].column).toBe(""); // invalid, cleared
  });

  it("handles legacy flat-rule shape (column at rule level)", () => {
    const { hadStale, patched } = clean("conditionalColumn", {
      rules: [
        { column: "gone", operator: "==", value: "x", result: "y" },
        { column: "name", operator: "==", value: "Alice", result: "z" },
      ],
      new_column: "label",
    });
    expect(hadStale).toBe(true);
    const rules = patched.rules as any[];
    expect(rules[0].column).toBe("");
    expect(rules[1].column).toBe("name");
  });

  it("no-op when all rule columns are valid", () => {
    expectClean("conditionalColumn", {
      rules: [
        { match: "all", conditions: [{ column: "age", operator: ">", value: "18" }], result: "adult" },
      ],
      new_column: "category",
    });
  });

  it("handles a rule with multiple conditions — clears only stale ones", () => {
    const { hadStale, patched } = clean("conditionalColumn", {
      rules: [
        {
          match: "all",
          conditions: [
            { column: "age", operator: ">", value: "18" },
            { column: "gone", operator: "!=", value: "" },
            { column: "score", operator: "<", value: "100" },
          ],
          result: "match",
        },
      ],
      new_column: "result",
    });
    expect(hadStale).toBe(true);
    const conds = (patched.rules as any[])[0].conditions;
    expect(conds[0].column).toBe("age");
    expect(conds[1].column).toBe(""); // stale
    expect(conds[2].column).toBe("score");
  });

  it("no-op when rules array is empty", () => {
    expectClean("conditionalColumn", { rules: [], new_column: "x" });
  });
});

describe("cleanStaleColumnRefs — mlTrain", () => {
  it("clears stale feature_columns and target_column", () => {
    const { hadStale, patched } = clean("mlTrainClassifier", {
      model_type: "random_forest",
      feature_columns: ["age", "missing_feature", "score"],
      target_column: "gone_label",
    });
    expect(hadStale).toBe(true);
    expect(patched.feature_columns).toEqual(["age", "score"]);
    expect(patched.target_column).toBe("");
  });

  it("preserves valid feature_columns and target_column", () => {
    expectClean("mlTrainRegressor", {
      model_type: "linear_regression",
      feature_columns: ["age", "score"],
      target_column: "name",
    });
  });

  it("handles absent feature_columns gracefully", () => {
    const { hadStale } = clean("mlTrainClassifier", { model_type: "svm", target_column: "name" });
    expect(hadStale).toBe(false);
  });
});

describe("cleanStaleColumnRefs — mixed valid/invalid", () => {
  it("reports hadStale=true when at least one field has a stale ref, even if others are clean", () => {
    const { hadStale, patched } = clean("groupByAggregate", {
      group_by: ["name", "gone"],
      aggregations: { age: "sum" }, // all valid
    });
    expect(hadStale).toBe(true);
    expect(patched.group_by).toEqual(["name"]);
    expect(patched.aggregations).toEqual({ age: "sum" }); // unchanged
  });

  it("preserves non-column config keys in all cases", () => {
    const { patched } = clean("filterRows", {
      column: "gone",
      operator: "between",
      value: "10",
      value2: "99",
    });
    expect(patched.operator).toBe("between");
    expect(patched.value).toBe("10");
    expect(patched.value2).toBe("99");
  });
});
