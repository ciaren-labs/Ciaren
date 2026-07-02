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
  "fileInput",
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
  "filterExpression",
  "combineColumns",
  "coalesceColumns",
  "explodeRows",
  "rollingAggregate",
  "rowDifference",
  "dateDifference",
  "assertValuesInSet",
  "pythonTransform",
  "jsonInput",
  "textInput",
  "sqlInput",
  "sqlOutput",
  "storageInput",
  "storageOutput",
  "fileOutput",
  "csvOutput",
  "excelOutput",
  "parquetOutput",
  "trainTestSplit",
  "scaleFeatures",
  "encodeCategories",
  "selectFeatures",
  "reduceDimensions",
  "mlClassifierModel",
  "mlRegressorModel",
  "mlTrainClassifier",
  "mlTrainRegressor",
  "mlTrainClustering",
  "mlTrainForecaster",
  "mlTrainDimReduction",
  "mlPredict",
  "mlEvaluate",
  "featureImportance",
  "mlCrossValidate",
  "assertNotNull",
  "assertUnique",
  "assertValueRange",
  "assertExpression",
  "assertRowCount",
]);

describe("nodeConfigSchemas coverage guard", () => {
  it("has a test for every registered node type", () => {
    const registered = Object.keys(nodeConfigSchemas);
    const missing = registered.filter((k) => !COVERED.has(k));
    expect(missing).toEqual([]);
  });
});

// Input nodes -----------------------------------------------------------
describe("input schemas (csv/excel/parquet/json/text)", () => {
  describe("fileInput", () => {
    it("accepts a chosen dataset and format", () => {
      accepts("fileInput", { dataset_id: "ds-1", format: "parquet" });
    });
    it("rejects an unknown format", () => {
      rejects("fileInput", { dataset_id: "ds-1", format: "xml" }, "format");
    });
  });

  for (const type of ["csvInput", "excelInput", "parquetInput", "jsonInput", "textInput"]) {
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
  it("accepts an n", () => accepts("sampleRows", { n: 10, seed: 42 }));
  it("accepts a frac", () => accepts("sampleRows", { frac: 0.25, seed: 42 }));
  it("rejects a missing seed (reproducibility)", () => rejects("sampleRows", { n: 10 }, "seed"));
  it("rejects neither n nor frac (superRefine)", () => rejects("sampleRows", { seed: 42 }, "n"));
  it("rejects a frac above 1", () => rejects("sampleRows", { frac: 1.5, seed: 42 }, "frac"));
  it("rejects a frac of 0", () => rejects("sampleRows", { frac: 0, seed: 42 }, "frac"));
});

// Quality / assertion nodes --------------------------------------------
describe("assertNotNull", () => {
  it("accepts empty config (defaults to all columns, error mode)", () => accepts("assertNotNull", {}));
  it("accepts columns + mode", () => accepts("assertNotNull", { columns: ["a"], mode: "warn" }));
  it("rejects an unknown mode", () => rejects("assertNotNull", { mode: "boom" }, "mode"));
});

describe("assertUnique", () => {
  it("accepts empty config", () => accepts("assertUnique", {}));
  it("rejects an unknown mode", () => rejects("assertUnique", { mode: "boom" }, "mode"));
});

describe("assertValueRange", () => {
  it("accepts a column with a min", () => accepts("assertValueRange", { column: "x", min: 0 }));
  it("accepts a column with a max", () => accepts("assertValueRange", { column: "x", max: 10 }));
  it("rejects a missing column", () => rejects("assertValueRange", { min: 0 }, "column"));
  it("rejects neither min nor max (superRefine)", () => rejects("assertValueRange", { column: "x" }, "min"));
});

describe("assertExpression", () => {
  it("accepts a non-empty expression", () => accepts("assertExpression", { expression: "amount > 0" }));
  it("rejects an empty expression", () => rejects("assertExpression", { expression: "" }, "expression"));
});

describe("assertRowCount", () => {
  it("accepts a min_rows", () => accepts("assertRowCount", { min_rows: 1 }));
  it("accepts a max_rows", () => accepts("assertRowCount", { max_rows: 100 }));
  it("rejects neither bound (superRefine)", () => rejects("assertRowCount", {}, "min_rows"));
  it("rejects min_rows > max_rows", () => rejects("assertRowCount", { min_rows: 10, max_rows: 5 }, "min_rows"));
  it("rejects a negative min_rows", () => rejects("assertRowCount", { min_rows: -1 }, "min_rows"));
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

// Advanced --------------------------------------------------------------
describe("pythonTransform", () => {
  it("accepts a non-empty script", () => accepts("pythonTransform", { script: "return df" }));
  it("rejects an empty script", () => rejects("pythonTransform", { script: "" }, "script"));
  it("rejects a missing script", () => rejects("pythonTransform", {}, "script"));
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

// Storage I/O (added alongside the storage connectors) -------------------
describe("storageInput", () => {
  it("accepts a full config", () =>
    accepts("storageInput", { connection_id: "c1", path: "data/in.csv", format: "csv" }));
  it("rejects a missing connection", () =>
    rejects("storageInput", { connection_id: "", path: "x", format: "csv" }, "connection_id"));
  it("rejects a missing path", () =>
    rejects("storageInput", { connection_id: "c1", path: "", format: "csv" }, "path"));
  it("rejects a bad format", () =>
    rejects("storageInput", { connection_id: "c1", path: "x", format: "avro" }, "format"));
});

describe("storageOutput", () => {
  it("accepts a full config", () =>
    accepts("storageOutput", { connection_id: "c1", path: "out.parquet", format: "parquet", if_exists: "overwrite" }));
  it("rejects a missing path", () =>
    rejects("storageOutput", { connection_id: "c1", path: "", format: "csv" }, "path"));
});

// Machine-learning nodes ------------------------------------------------
describe("trainTestSplit", () => {
  it("accepts a valid split", () =>
    accepts("trainTestSplit", { test_size: 0.2, stratify_column: "target", seed: 42 }));
  it("accepts a null stratify column", () =>
    accepts("trainTestSplit", { test_size: 0.3, stratify_column: null, seed: 1 }));
  it("rejects test_size of 0 or 1", () => {
    rejects("trainTestSplit", { test_size: 0, seed: 1 }, "test_size");
    rejects("trainTestSplit", { test_size: 1, seed: 1 }, "test_size");
  });
  it("requires a seed", () => rejects("trainTestSplit", { test_size: 0.2 }, "seed"));
  it("requires an integer seed", () =>
    rejects("trainTestSplit", { test_size: 0.2, seed: 1.5 }, "seed"));
});

describe("scaleFeatures", () => {
  it("accepts a method + columns", () =>
    accepts("scaleFeatures", { method: "standard", columns: ["a", "b"] }));
  it("rejects an empty column list", () =>
    rejects("scaleFeatures", { method: "minmax", columns: [] }, "columns"));
  it("rejects a bad method", () =>
    rejects("scaleFeatures", { method: "zscore", columns: ["a"] }, "method"));
});

describe("encodeCategories", () => {
  it("accepts onehot with drop_first", () =>
    accepts("encodeCategories", { method: "onehot", columns: ["c"], drop_first: true }));
  it("accepts ordinal", () => accepts("encodeCategories", { method: "ordinal", columns: ["c"] }));
  it("rejects a bad method", () =>
    rejects("encodeCategories", { method: "binary", columns: ["c"] }, "method"));
});

describe("selectFeatures", () => {
  it("accepts variance", () => accepts("selectFeatures", { method: "variance", threshold: 0 }));
  it("accepts correlation", () =>
    accepts("selectFeatures", { method: "correlation", threshold: 0.9 }));
  it("accepts kbest with target + k", () =>
    accepts("selectFeatures", { method: "kbest", target_column: "y", k: 5 }));
  it("rejects kbest without a target (superRefine)", () =>
    rejects("selectFeatures", { method: "kbest", k: 5 }, "target_column"));
  it("rejects kbest without k (superRefine)", () =>
    rejects("selectFeatures", { method: "kbest", target_column: "y" }, "k"));
});

describe("reduceDimensions", () => {
  it("accepts an int component count", () =>
    accepts("reduceDimensions", { method: "pca", n_components: 3 }));
  it("accepts a variance fraction", () =>
    accepts("reduceDimensions", { method: "pca", n_components: 0.95 }));
  it("rejects a non-positive n_components", () =>
    rejects("reduceDimensions", { method: "pca", n_components: 0 }, "n_components"));
  it("rejects a non-pca method", () =>
    rejects("reduceDimensions", { method: "tsne", n_components: 2 }, "method"));
});

describe("mlTrainClassifier", () => {
  it("accepts a supervised config with a target", () =>
    accepts("mlTrainClassifier", {
      model_type: "random_forest_classifier",
      target_column: "churn",
      feature_columns: ["a", "b"],
      seed: 42,
    }));
  it("accepts an unsupervised model without a target", () =>
    accepts("mlTrainRegressor", { model_type: "kmeans", seed: 1 }));
  it("requires a seed", () =>
    rejects("mlTrainRegressor", { model_type: "ridge", target_column: "y" }, "seed"));
  // Plugins can contribute model types beyond the static mirror, so any
  // non-empty model_type passes here (the backend catalog re-validates); only
  // a missing/empty model type is a form error.
  it("accepts a plugin-contributed model_type", () =>
    accepts("mlTrainRegressor", { model_type: "deep_net", target_column: "y", seed: 1 }));
  it("rejects an empty model_type", () =>
    rejects("mlTrainRegressor", { model_type: "", target_column: "y", seed: 1 }, "model_type"));
  it("requires a target for supervised models (superRefine)", () =>
    rejects("mlTrainRegressor", { model_type: "ridge", seed: 1 }, "target_column"));
  it("rejects the target appearing in features (leakage)", () =>
    rejects(
      "mlTrainRegressor",
      { model_type: "ridge", target_column: "y", feature_columns: ["x", "y"], seed: 1 },
      "feature_columns",
    ));
});

describe("mlPredict", () => {
  it("accepts an output column", () => accepts("mlPredict", { output_column: "prediction" }));
  it("accepts a model_uri + proba columns", () =>
    accepts("mlPredict", {
      model_uri: "models:/churn/Production",
      output_column: "yhat",
      output_proba_columns: ["p0", "p1"],
    }));
  it("rejects a missing output column", () =>
    rejects("mlPredict", { output_column: "" }, "output_column"));
});

describe("mlEvaluate", () => {
  it("accepts classification with a target", () =>
    accepts("mlEvaluate", {
      task_type: "classification",
      target_column: "y",
      prediction_column: "prediction",
    }));
  it("accepts clustering without a target", () =>
    accepts("mlEvaluate", { task_type: "clustering", prediction_column: "cluster" }));
  it("rejects a bad task_type", () =>
    rejects("mlEvaluate", { task_type: "ranking", prediction_column: "p" }, "task_type"));
  it("requires a target for non-clustering (superRefine)", () =>
    rejects("mlEvaluate", { task_type: "regression", prediction_column: "p" }, "target_column"));
});

describe("featureImportance", () => {
  it("accepts an empty config", () => accepts("featureImportance", {}));
  it("accepts a top_n", () => accepts("featureImportance", { top_n: 10 }));
  it("rejects a top_n below 1", () => rejects("featureImportance", { top_n: 0 }, "top_n"));
});

describe("mlCrossValidate", () => {
  it("accepts a k-fold config", () =>
    accepts("mlCrossValidate", {
      cv_strategy: "kfold",
      n_splits: 5,
      seed: 42,
    }));
  it("requires a seed", () => rejects("mlCrossValidate", { cv_strategy: "kfold" }, "seed"));
  it("rejects an unknown strategy", () =>
    rejects(
      "mlCrossValidate",
      { cv_strategy: "bogus", seed: 1 },
      "cv_strategy",
    ));
  it("requires a group column for group k-fold", () =>
    rejects(
      "mlCrossValidate",
      { cv_strategy: "group_kfold", seed: 1 },
      "group_column",
    ));
});

describe("filterExpression", () => {
  it("accepts a non-empty expression", () => accepts("filterExpression", { expression: "a > 1" }));
  it("rejects an empty expression", () => rejects("filterExpression", { expression: "" }, "expression"));
});

describe("combineColumns", () => {
  it("accepts two+ columns and a name", () =>
    accepts("combineColumns", { columns: ["a", "b"], new_column: "c", separator: "-" }));
  it("rejects fewer than two columns", () =>
    rejects("combineColumns", { columns: ["a"], new_column: "c" }, "columns"));
  it("requires a new column name", () => rejects("combineColumns", { columns: ["a", "b"] }, "new_column"));
});

describe("coalesceColumns", () => {
  it("accepts two+ columns and a name", () =>
    accepts("coalesceColumns", { columns: ["a", "b"], new_column: "c" }));
  it("rejects fewer than two columns", () =>
    rejects("coalesceColumns", { columns: ["a"], new_column: "c" }, "columns"));
});

describe("explodeRows", () => {
  it("accepts a column with a delimiter", () => accepts("explodeRows", { column: "tags", delimiter: ";" }));
  it("accepts a column without a delimiter (list column)", () => accepts("explodeRows", { column: "tags" }));
  it("requires a column", () => rejects("explodeRows", { delimiter: ";" }, "column"));
});

describe("rollingAggregate", () => {
  it("accepts a valid config", () =>
    accepts("rollingAggregate", { target: "v", function: "mean", window: 3, order_by: ["t"], new_column: "r" }));
  it("rejects an unknown function", () =>
    rejects("rollingAggregate", { target: "v", function: "variance", window: 3, new_column: "r" }, "function"));
  it("rejects a window below 1", () =>
    rejects("rollingAggregate", { target: "v", function: "mean", window: 0, new_column: "r" }, "window"));
  it("requires target and new column", () =>
    rejects("rollingAggregate", { function: "mean", window: 3 }, "target"));
});

describe("rowDifference", () => {
  it("accepts diff and pct_change", () => {
    accepts("rowDifference", { target: "v", method: "diff", new_column: "d" });
    accepts("rowDifference", { target: "v", method: "pct_change", periods: 2, new_column: "p" });
  });
  it("rejects an unknown method", () =>
    rejects("rowDifference", { target: "v", method: "delta", new_column: "d" }, "method"));
  it("rejects periods below 1", () =>
    rejects("rowDifference", { target: "v", method: "diff", periods: 0, new_column: "d" }, "periods"));
});

describe("dateDifference", () => {
  it("accepts two columns, a unit and a name", () =>
    accepts("dateDifference", { start_column: "s", end_column: "e", unit: "days", new_column: "d" }));
  it("rejects an unknown unit", () =>
    rejects("dateDifference", { start_column: "s", end_column: "e", unit: "months", new_column: "d" }, "unit"));
  it("requires the end column", () =>
    rejects("dateDifference", { start_column: "s", unit: "days", new_column: "d" }, "end_column"));
});

describe("assertValuesInSet", () => {
  it("accepts a column and an allowed set", () =>
    accepts("assertValuesInSet", { column: "status", allowed: ["paid", "pending"], mode: "error" }));
  it("rejects an empty allowed set", () =>
    rejects("assertValuesInSet", { column: "status", allowed: [] }, "allowed"));
  it("requires a column", () => rejects("assertValuesInSet", { allowed: ["a"] }, "column"));
});
