import { describe, expect, it } from "vitest";
import { nodeConfigSchemas } from "../validators";

// Helpers ---------------------------------------------------------------
function accepts(type: string, config: unknown) {
  const result = nodeConfigSchemas[type].safeParse(config);
  if (!result.success) {
    // Surface why so a failing test is debuggable.
    throw new Error(
      `Expected ${type} config to be ACCEPTED but it was rejected: ${JSON.stringify(
        result.error.issues,
      )}`,
    );
  }
  expect(result.success).toBe(true);
}

function rejects(type: string, config: unknown, pathContains?: string) {
  const result = nodeConfigSchemas[type].safeParse(config);
  expect(result.success).toBe(false);
  if (!result.success && pathContains) {
    const paths = result.error.issues.map((i) => i.path.join("."));
    expect(paths.some((p) => p.includes(pathContains))).toBe(true);
  }
}

// Every key in the registry must be covered by this file. This guard fails
// loudly if a new node type is added without a test.
const COVERED = new Set<string>([
  "csvInput",
  "excelInput",
  "parquetInput",
  "dropNulls",
  "fillNulls",
  "dropColumns",
  "renameColumns",
  "selectColumns",
  "removeDuplicates",
  "filterRows",
  "sortRows",
  "castDtypes",
  "limitRows",
  "replaceValues",
  "stringTransform",
  "calculatedColumn",
  "groupByAggregate",
  "join",
  "concatRows",
  "sampleRows",
  "removeOutliers",
  "roundNumbers",
  "binColumn",
  "extractDateParts",
  "unpivot",
  "pivot",
  "splitColumn",
  "parseDates",
  "mapValues",
  "windowFunction",
  "conditionalColumn",
  "sqlInput",
  "sqlOutput",
  "csvOutput",
  "excelOutput",
  "parquetOutput",
]);

describe("nodeConfigSchemas coverage guard", () => {
  it("has a test for every registered node type", () => {
    const registered = Object.keys(nodeConfigSchemas);
    const missing = registered.filter((k) => !COVERED.has(k));
    expect(missing).toEqual([]);
  });
});

// Input nodes -----------------------------------------------------------
describe("input schemas (csv/excel/parquet)", () => {
  for (const type of ["csvInput", "excelInput", "parquetInput"]) {
    describe(type, () => {
      it("accepts a chosen dataset", () => {
        accepts(type, { dataset_id: "ds-1" });
      });
      it("accepts a pinned version", () => {
        accepts(type, { dataset_id: "ds-1", dataset_version: 3 });
      });
      it("accepts a null version (latest)", () => {
        accepts(type, { dataset_id: "ds-1", dataset_version: null });
      });
      it("rejects a missing dataset id", () => {
        rejects(type, { dataset_id: "" }, "dataset_id");
      });
      it("rejects a non-positive / non-integer version", () => {
        rejects(type, { dataset_id: "ds-1", dataset_version: 0 }, "dataset_version");
        rejects(type, { dataset_id: "ds-1", dataset_version: 1.5 }, "dataset_version");
      });
    });
  }
});

// Cleaning nodes --------------------------------------------------------
describe("dropNulls", () => {
  it("accepts an empty config (check all columns)", () => accepts("dropNulls", {}));
  it("accepts subset + how", () => accepts("dropNulls", { subset: ["a"], how: "all" }));
  it("rejects a bad how enum", () => rejects("dropNulls", { how: "some" }, "how"));
  it("rejects a non-string subset entry", () => rejects("dropNulls", { subset: [1] }, "subset"));
});

describe("fillNulls", () => {
  it("accepts an empty config (legacy constant)", () => accepts("fillNulls", {}));
  it("accepts a strategy + columns", () =>
    accepts("fillNulls", { strategy: "mean", columns: ["a"] }));
  it("accepts the constant strategy with a value", () =>
    accepts("fillNulls", { strategy: "constant", value: "0" }));
  it("rejects a bad strategy", () => rejects("fillNulls", { strategy: "nope" }, "strategy"));
});

describe("dropColumns", () => {
  it("accepts at least one column", () => accepts("dropColumns", { columns: ["a"] }));
  it("rejects an empty column list", () => rejects("dropColumns", { columns: [] }, "columns"));
  it("rejects a missing column list", () => rejects("dropColumns", {}, "columns"));
});

describe("renameColumns", () => {
  it("accepts a mapping", () => accepts("renameColumns", { mapping: { old: "new" } }));
  it("accepts an empty mapping (UX-lenient)", () => accepts("renameColumns", { mapping: {} }));
  it("rejects a non-record mapping", () => rejects("renameColumns", { mapping: "x" }, "mapping"));
  it("rejects a non-string mapping value", () =>
    rejects("renameColumns", { mapping: { a: 1 } }, "mapping"));
});

describe("selectColumns", () => {
  it("accepts at least one column", () => accepts("selectColumns", { columns: ["a", "b"] }));
  it("rejects an empty column list", () => rejects("selectColumns", { columns: [] }, "columns"));
});

describe("removeDuplicates", () => {
  it("accepts an empty config", () => accepts("removeDuplicates", {}));
  it("accepts subset + keep", () =>
    accepts("removeDuplicates", { subset: ["a"], keep: "last" }));
  it("rejects a bad keep enum", () => rejects("removeDuplicates", { keep: "both" }, "keep"));
});

describe("filterRows", () => {
  it("accepts a simple comparison", () =>
    accepts("filterRows", { column: "a", operator: ">", value: 5 }));
  it("accepts a valueless operator (isnull)", () =>
    accepts("filterRows", { column: "a", operator: "isnull" }));
  it("accepts a 'between' with an upper bound", () =>
    accepts("filterRows", { column: "a", operator: "between", value: 1, value2: 9 }));
  it("rejects a missing column", () =>
    rejects("filterRows", { column: "", operator: "==", value: 1 }, "column"));
  it("rejects a bad operator", () =>
    rejects("filterRows", { column: "a", operator: "~=", value: 1 }, "operator"));
  it("rejects 'between' without an upper bound (superRefine)", () =>
    rejects("filterRows", { column: "a", operator: "between", value: 1 }, "value2"));
  it("rejects 'between' with an empty-string upper bound", () =>
    rejects("filterRows", { column: "a", operator: "between", value: 1, value2: "" }, "value2"));
});

describe("sortRows", () => {
  it("accepts columns + options", () =>
    accepts("sortRows", { columns: ["a"], ascending: false, na_position: "first" }));
  it("rejects an empty column list", () => rejects("sortRows", { columns: [] }, "columns"));
  it("rejects a bad na_position", () =>
    rejects("sortRows", { columns: ["a"], na_position: "middle" }, "na_position"));
});

describe("castDtypes", () => {
  it("accepts casts + errors + format", () =>
    accepts("castDtypes", {
      casts: { a: "integer", b: "datetime" },
      errors: "coerce",
      format: "%Y-%m-%d",
    }));
  it("accepts an empty casts record (UX-lenient)", () => accepts("castDtypes", { casts: {} }));
  it("rejects a bad dtype value", () =>
    rejects("castDtypes", { casts: { a: "decimal" } }, "casts"));
  it("rejects a bad errors enum", () =>
    rejects("castDtypes", { casts: { a: "integer" }, errors: "ignore" }, "errors"));
});

describe("limitRows", () => {
  it("accepts a positive n", () => accepts("limitRows", { n: 100 }));
  it("coerces a numeric string n", () => accepts("limitRows", { n: "50", offset: "10" }));
  it("rejects n below 1", () => rejects("limitRows", { n: 0 }, "n"));
  it("rejects a negative offset", () => rejects("limitRows", { n: 10, offset: -1 }, "offset"));
  it("rejects a missing n", () => rejects("limitRows", {}, "n"));
});

describe("replaceValues", () => {
  it("accepts a full replace config", () =>
    accepts("replaceValues", { column: "a", to_replace: "x", value: "y", regex: true }));
  it("accepts empty find/replace strings", () =>
    accepts("replaceValues", { column: "a", to_replace: "", value: "" }));
  it("rejects a missing column", () =>
    rejects("replaceValues", { column: "", to_replace: "x", value: "y" }, "column"));
  it("rejects missing to_replace/value (required strings)", () =>
    rejects("replaceValues", { column: "a" }, "to_replace"));
});

describe("stringTransform", () => {
  it("accepts a simple operation", () =>
    accepts("stringTransform", { column: "a", operation: "upper" }));
  it("accepts replace with find", () =>
    accepts("stringTransform", { column: "a", operation: "replace", find: "x", replace_with: "y" }));
  it("accepts pad with width", () =>
    accepts("stringTransform", { column: "a", operation: "pad", width: 5, side: "left" }));
  it("rejects a missing column", () =>
    rejects("stringTransform", { column: "", operation: "lower" }, "column"));
  it("rejects a bad operation", () =>
    rejects("stringTransform", { column: "a", operation: "snake" }, "operation"));
  it("rejects replace without find (superRefine)", () =>
    rejects("stringTransform", { column: "a", operation: "replace" }, "find"));
  it("rejects pad without width (superRefine)", () =>
    rejects("stringTransform", { column: "a", operation: "pad" }, "width"));
});

describe("calculatedColumn", () => {
  it("accepts a name + expression", () =>
    accepts("calculatedColumn", { column_name: "total", expression: "price * qty" }));
  it("rejects a missing column name", () =>
    rejects("calculatedColumn", { column_name: "", expression: "x" }, "column_name"));
  it("rejects a missing expression", () =>
    rejects("calculatedColumn", { column_name: "total", expression: "" }, "expression"));
});

describe("groupByAggregate", () => {
  it("accepts group_by + aggregations", () =>
    accepts("groupByAggregate", { group_by: ["region"], aggregations: { sales: "sum" } }));
  it("rejects an empty group_by", () =>
    rejects("groupByAggregate", { group_by: [], aggregations: { sales: "sum" } }, "group_by"));
  it("rejects a missing aggregations record", () =>
    rejects("groupByAggregate", { group_by: ["region"] }, "aggregations"));
});

describe("join", () => {
  it("accepts a single 'on' key", () => accepts("join", { on: "id", how: "inner" }));
  it("accepts an array 'on'", () => accepts("join", { on: ["id", "date"], how: "left" }));
  it("accepts split left_on + right_on keys", () =>
    accepts("join", { left_on: ["id"], right_on: ["ref"], how: "outer" }));
  it("accepts suffixes of length 2", () =>
    accepts("join", { on: "id", how: "inner", suffixes: ["_x", "_y"] }));
  it("rejects a missing how", () => rejects("join", { on: "id" }, "how"));
  it("rejects a bad how enum", () => rejects("join", { on: "id", how: "cross" }, "how"));
  it("rejects no key at all (superRefine)", () => rejects("join", { how: "inner" }, "on"));
  it("rejects empty on + only left_on (superRefine)", () =>
    rejects("join", { left_on: ["id"], how: "inner" }, "on"));
  it("rejects suffixes that aren't length 2", () =>
    rejects("join", { on: "id", how: "inner", suffixes: ["_x"] }, "suffixes"));
});

describe("concatRows", () => {
  it("accepts an empty config", () => accepts("concatRows", {}));
});

// New transform nodes ---------------------------------------------------
describe("sampleRows", () => {
  it("accepts an n", () => accepts("sampleRows", { n: 10 }));
  it("accepts a frac", () => accepts("sampleRows", { frac: 0.25, seed: 42 }));
  it("rejects neither n nor frac (superRefine)", () => rejects("sampleRows", {}, "n"));
  it("rejects a frac above 1", () => rejects("sampleRows", { frac: 1.5 }, "frac"));
  it("rejects a frac of 0", () => rejects("sampleRows", { frac: 0 }, "frac"));
});

describe("removeOutliers", () => {
  it("accepts an iqr config", () =>
    accepts("removeOutliers", { columns: ["a"], method: "iqr", action: "drop", factor: 1.5 }));
  it("accepts a zscore config", () =>
    accepts("removeOutliers", { columns: ["a"], method: "zscore", action: "clip", threshold: 3 }));
  it("accepts a percentile config", () =>
    accepts("removeOutliers", {
      columns: ["a"],
      method: "percentile",
      action: "clip",
      lower: 1,
      upper: 99,
    }));
  it("rejects an empty column list", () =>
    rejects("removeOutliers", { columns: [], method: "iqr", action: "drop" }, "columns"));
  it("rejects a bad method", () =>
    rejects("removeOutliers", { columns: ["a"], method: "madness", action: "drop" }, "method"));
  it("rejects a bad action", () =>
    rejects("removeOutliers", { columns: ["a"], method: "iqr", action: "explode" }, "action"));
  it("rejects an upper percentile above 100", () =>
    rejects(
      "removeOutliers",
      { columns: ["a"], method: "percentile", action: "clip", upper: 101 },
      "upper",
    ));
});

describe("roundNumbers", () => {
  it("accepts columns + decimals", () =>
    accepts("roundNumbers", { columns: ["a"], decimals: 2 }));
  it("accepts 0 decimals", () => accepts("roundNumbers", { columns: ["a"], decimals: 0 }));
  it("rejects an empty column list", () =>
    rejects("roundNumbers", { columns: [], decimals: 2 }, "columns"));
  it("rejects negative decimals", () =>
    rejects("roundNumbers", { columns: ["a"], decimals: -1 }, "decimals"));
  it("rejects missing decimals", () =>
    rejects("roundNumbers", { columns: ["a"] }, "decimals"));
});

describe("binColumn", () => {
  it("accepts a full config", () =>
    accepts("binColumn", { column: "age", new_column: "bucket", method: "equalwidth", bins: 4 }));
  it("rejects a missing new_column", () =>
    rejects("binColumn", { column: "age", new_column: "", method: "quantile", bins: 4 }, "new_column"));
  it("rejects a bad method", () =>
    rejects("binColumn", { column: "age", new_column: "b", method: "log", bins: 4 }, "method"));
  it("rejects fewer than 2 bins", () =>
    rejects("binColumn", { column: "age", new_column: "b", method: "quantile", bins: 1 }, "bins"));
});

describe("extractDateParts", () => {
  it("accepts a column + parts", () =>
    accepts("extractDateParts", { column: "d", parts: ["year", "month"] }));
  it("rejects an empty parts list", () =>
    rejects("extractDateParts", { column: "d", parts: [] }, "parts"));
  it("rejects a bad part", () =>
    rejects("extractDateParts", { column: "d", parts: ["century"] }, "parts"));
  it("rejects a missing column", () =>
    rejects("extractDateParts", { column: "", parts: ["year"] }, "column"));
});

describe("unpivot", () => {
  it("accepts id_vars + options", () =>
    accepts("unpivot", {
      id_vars: ["id"],
      value_vars: ["jan", "feb"],
      var_name: "month",
      value_name: "amount",
    }));
  it("accepts id_vars only", () => accepts("unpivot", { id_vars: ["id"] }));
  it("rejects an empty id_vars", () => rejects("unpivot", { id_vars: [] }, "id_vars"));
});

describe("pivot", () => {
  it("accepts a full config", () =>
    accepts("pivot", { index: ["id"], columns: "metric", values: "amount", aggfunc: "sum" }));
  it("rejects an empty index", () =>
    rejects("pivot", { index: [], columns: "m", values: "v", aggfunc: "sum" }, "index"));
  it("rejects a missing values column", () =>
    rejects("pivot", { index: ["id"], columns: "m", values: "", aggfunc: "sum" }, "values"));
  it("rejects a bad aggfunc", () =>
    rejects("pivot", { index: ["id"], columns: "m", values: "v", aggfunc: "concat" }, "aggfunc"));
});

describe("splitColumn", () => {
  it("accepts a delimiter split", () =>
    accepts("splitColumn", { column: "name", mode: "delimiter", delimiter: " ", into: ["first", "last"] }));
  it("accepts a regex split", () =>
    accepts("splitColumn", { column: "code", mode: "regex", pattern: "(\\d+)-(\\d+)", into: ["a", "b"] }));
  it("rejects an empty 'into' list", () =>
    rejects("splitColumn", { column: "name", mode: "delimiter", delimiter: " ", into: [] }, "into"));
  it("rejects a bad mode", () =>
    rejects("splitColumn", { column: "name", mode: "slice", into: ["a"] }, "mode"));
  it("rejects delimiter mode without a delimiter (superRefine)", () =>
    rejects("splitColumn", { column: "name", mode: "delimiter", into: ["a"] }, "delimiter"));
  it("rejects regex mode without a pattern (superRefine)", () =>
    rejects("splitColumn", { column: "name", mode: "regex", into: ["a"] }, "pattern"));
});

describe("parseDates", () => {
  it("accepts columns + options", () =>
    accepts("parseDates", { columns: ["d"], format: "%Y-%m-%d", errors: "coerce" }));
  it("rejects an empty column list", () => rejects("parseDates", { columns: [] }, "columns"));
  it("rejects a bad errors enum", () =>
    rejects("parseDates", { columns: ["d"], errors: "skip" }, "errors"));
});

describe("mapValues", () => {
  it("accepts a non-empty mapping", () =>
    accepts("mapValues", { column: "a", mapping: { yes: "1", no: "0" } }));
  it("accepts a default", () =>
    accepts("mapValues", { column: "a", mapping: { yes: "1" }, use_default: true, default: "0" }));
  it("rejects a missing column", () =>
    rejects("mapValues", { column: "", mapping: { a: "b" } }, "column"));
  it("rejects an empty mapping (superRefine)", () =>
    rejects("mapValues", { column: "a", mapping: {} }, "mapping"));
});

describe("windowFunction", () => {
  it("accepts row_number with a new column", () =>
    accepts("windowFunction", { function: "row_number", new_column: "rn" }));
  it("accepts a target-needing function with a target", () =>
    accepts("windowFunction", {
      function: "cumsum",
      target: "amount",
      new_column: "running_total",
    }));
  it("accepts a rank function with an order_by", () =>
    accepts("windowFunction", { function: "rank", order_by: ["score"], new_column: "rank" }));
  it("rejects a missing new column", () =>
    rejects("windowFunction", { function: "row_number", new_column: "" }, "new_column"));
  it("rejects a target function without a target (superRefine)", () =>
    rejects("windowFunction", { function: "lag", new_column: "prev" }, "target"));
  it("rejects a rank function without an order_by (superRefine)", () =>
    rejects("windowFunction", { function: "dense_rank", new_column: "r" }, "order_by"));
});

describe("conditionalColumn", () => {
  const schema = nodeConfigSchemas.conditionalColumn;

  it("accepts a numeric rule value (e.g. line_total >= 5000)", () => {
    const result = schema.safeParse({
      new_column: "revenue_tier",
      default: "low",
      rules: [{ column: "line_total", operator: ">=", value: 5000, result: "high" }],
    });
    expect(result.success).toBe(true);
  });

  it("still accepts a legacy flat rule (string value)", () => {
    const result = schema.safeParse({
      new_column: "flag",
      rules: [{ column: "status", operator: "==", value: "active", result: "yes" }],
    });
    expect(result.success).toBe(true);
  });

  it("accepts a rule with multiple AND/OR conditions", () => {
    const result = schema.safeParse({
      new_column: "segment",
      default: "other",
      rules: [
        {
          match: "all",
          conditions: [
            { column: "age", operator: ">=", value: 18 },
            { column: "country", operator: "==", value: "US" },
          ],
          result: "us_adult",
        },
      ],
    });
    expect(result.success).toBe(true);
  });

  it("rejects a missing new column", () =>
    rejects("conditionalColumn", {
      new_column: "",
      rules: [{ column: "a", operator: "==", value: "x" }],
    }, "new_column"));

  it("rejects an empty rules list", () =>
    rejects("conditionalColumn", { new_column: "seg", rules: [] }, "rules"));

  it("rejects a rule with neither conditions nor a legacy column", () => {
    const result = schema.safeParse({
      new_column: "segment",
      rules: [{ result: "x" }],
    });
    expect(result.success).toBe(false);
  });
});

// SQL + output nodes ----------------------------------------------------
describe("sqlInput", () => {
  it("accepts table mode with a table", () =>
    accepts("sqlInput", { connection_id: "c1", mode: "table", table: "orders" }));
  it("accepts table mode by default (no mode)", () =>
    accepts("sqlInput", { connection_id: "c1", table: "orders" }));
  it("accepts query mode with a query", () =>
    accepts("sqlInput", { connection_id: "c1", mode: "query", query: "SELECT 1" }));
  it("rejects a missing connection", () =>
    rejects("sqlInput", { mode: "table", table: "orders" }, "connection_id"));
  it("rejects table mode without a table (superRefine)", () =>
    rejects("sqlInput", { connection_id: "c1", mode: "table" }, "table"));
  it("rejects query mode with a blank query (superRefine)", () =>
    rejects("sqlInput", { connection_id: "c1", mode: "query", query: "   " }, "query"));
});

describe("sqlOutput", () => {
  it("accepts a full config", () =>
    accepts("sqlOutput", { connection_id: "c1", table: "out", if_exists: "append" }));
  it("rejects a missing connection", () =>
    rejects("sqlOutput", { connection_id: "", table: "out" }, "connection_id"));
  it("rejects a missing table", () =>
    rejects("sqlOutput", { connection_id: "c1", table: "" }, "table"));
  it("rejects a bad if_exists", () =>
    rejects("sqlOutput", { connection_id: "c1", table: "out", if_exists: "merge" }, "if_exists"));
});

describe("file output schemas (csv/excel/parquet)", () => {
  for (const type of ["csvOutput", "excelOutput", "parquetOutput"]) {
    describe(type, () => {
      it("accepts a dataset name", () => accepts(type, { dataset_name: "cleaned" }));
      it("rejects an empty dataset name", () =>
        rejects(type, { dataset_name: "" }, "dataset_name"));
      it("rejects a missing dataset name", () => rejects(type, {}, "dataset_name"));
    });
  }
});
