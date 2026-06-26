// Zod schemas for validating each node type's config in the sidebar forms.
import { z } from "zod";
import { ML_MODEL_VALUES, isSupervisedModel } from "./mlModels";

const stringArray = z.array(z.string());

export const filterOperators = [
  "==",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
  "between",
  "in",
  "contains",
  "startswith",
  "endswith",
  "isnull",
  "notnull",
] as const;

// Fill-null strategies. "constant" uses the typed value; the rest are computed
// per column. Labels drive the strategy <Select> in the node config form.
export const fillStrategies = [
  { value: "constant", label: "Constant value" },
  { value: "mean", label: "Mean (average)" },
  { value: "median", label: "Median" },
  { value: "mode", label: "Most frequent (mode)" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
  { value: "zero", label: "Zero" },
  { value: "ffill", label: "Forward fill" },
  { value: "bfill", label: "Backward fill" },
] as const;

export const fillStrategyValues = fillStrategies.map((s) => s.value) as [
  string,
  ...string[],
];

export const stringOperations = [
  "lower",
  "upper",
  "strip",
  "title",
  "capitalize",
  "len",
  "replace",
  "pad",
] as const;

// Operations needing extra inputs, so the form can render them conditionally.
export const STRING_OPS_WITH_FIND = new Set(["replace"]);
export const STRING_OPS_WITH_PAD = new Set(["pad"]);

export const aggFunctions = [
  "sum",
  "mean",
  "count",
  "min",
  "max",
  "median",
  "nunique",
  "std",
  "var",
  "first",
  "last",
] as const;

export const joinHows = ["inner", "left", "right", "outer"] as const;

export const FILTER_OPERATOR_LABELS: Record<string, string> = {
  "==": "= equals",
  "!=": "≠ not equals",
  ">": "> greater than",
  ">=": "≥ greater or equal",
  "<": "< less than",
  "<=": "≤ less or equal",
  between: "between (range)",
  in: "in (list of values)",
  contains: "contains (text)",
  startswith: "starts with",
  endswith: "ends with",
  isnull: "is null / empty",
  notnull: "is not null / not empty",
};

export const STRING_OPERATION_LABELS: Record<string, string> = {
  lower: "Lowercase (abc)",
  upper: "Uppercase (ABC)",
  strip: "Strip whitespace",
  title: "Title Case (Abc Def)",
  capitalize: "Capitalize first letter",
  len: "String length (count characters)",
  replace: "Find & Replace",
  pad: "Pad to fixed width",
};

export const JOIN_HOW_LABELS: Record<string, string> = {
  inner: "Inner — keep only matching rows",
  left: "Left — all left rows, matched right",
  right: "Right — all right rows, matched left",
  outer: "Full outer — all rows from both sides",
};

export const OUTLIER_METHOD_LABELS: Record<string, string> = {
  iqr: "IQR (interquartile range)",
  zscore: "Z-score (standard deviations from mean)",
  percentile: "Percentile (custom % bounds)",
};

export const outlierMethods = ["iqr", "zscore", "percentile"] as const;
export const outlierActions = ["drop", "clip"] as const;
export const binMethods = ["equalwidth", "quantile"] as const;
export const splitModes = ["delimiter", "regex"] as const;
export const dateParts = ["year", "month", "day", "weekday", "hour"] as const;

export const windowFunctions = [
  "row_number",
  "rank",
  "dense_rank",
  "cumcount",
  "cumsum",
  "cummax",
  "cummin",
  "lag",
  "lead",
] as const;
// Functions that operate on a value column, and those that need an order key.
export const windowTargetFuncs = new Set(["cumsum", "cummax", "cummin", "lag", "lead"]);
export const windowRankFuncs = new Set(["rank", "dense_rank"]);

// Operators usable in a conditionalColumn rule.
export const conditionOperators = [
  "==",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
  "contains",
  "startswith",
  "endswith",
  "isnull",
  "notnull",
] as const;
export const conditionValueless = new Set(["isnull", "notnull"]);

// One condition inside a conditionalColumn rule. The value compares against a
// numeric column with a number (e.g. amount >= 5000) or a text column with a
// string, so accept either.
const conditionSchema = z.object({
  column: z.string().min(1, "Column is required"),
  operator: z.enum(conditionOperators),
  value: z.union([z.string(), z.number()]).optional(),
});
export const dtypes = [
  "integer",
  "float",
  "boolean",
  "string",
  "datetime",
] as const;

const inputConfig = z.object({
  dataset_id: z.string().min(1, "Select a dataset"),
  // Pinned version number; null/absent means "use latest".
  dataset_version: z.number().int().positive().nullable().optional(),
});

export const nodeConfigSchemas: Record<string, z.ZodTypeAny> = {
  csvInput: inputConfig,
  excelInput: inputConfig,
  parquetInput: inputConfig,
  jsonInput: inputConfig,
  textInput: inputConfig,

  dropNulls: z.object({
    subset: stringArray.optional(),
    how: z.enum(["any", "all"]).optional(),
  }),
  fillNulls: z.object({
    // Absent strategy means the legacy "constant" fill, using `value`.
    strategy: z.enum(fillStrategyValues).optional(),
    value: z.string().optional(),
    columns: stringArray.optional(),
  }),
  dropColumns: z.object({
    columns: stringArray.min(1, "Add at least one column"),
  }),
  renameColumns: z.object({
    mapping: z.record(z.string(), z.string()),
  }),
  selectColumns: z.object({
    columns: stringArray.min(1, "Add at least one column"),
  }),
  removeDuplicates: z.object({
    subset: stringArray.optional(),
    keep: z.enum(["first", "last"]).optional(),
  }),
  filterRows: z
    .object({
      column: z.string().min(1, "Column is required"),
      operator: z.enum(filterOperators),
      // A comparison against a numeric column uses a number; text uses a string.
      value: z.union([z.string(), z.number()]).optional(),
      // Upper bound, only used by the "between" operator.
      value2: z.union([z.string(), z.number()]).optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.operator === "between" && (cfg.value2 == null || cfg.value2 === "")) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["value2"],
          message: "An upper bound is required for 'between'",
        });
      }
    }),
  sortRows: z.object({
    columns: stringArray.min(1, "Add at least one column"),
    ascending: z.boolean().optional(),
    na_position: z.enum(["first", "last"]).optional(),
  }),
  castDtypes: z.object({
    casts: z.record(z.string(), z.enum(dtypes)),
    errors: z.enum(["raise", "coerce"]).optional(),
    format: z.string().optional(),
  }),
  limitRows: z.object({
    n: z.coerce.number().int().min(1, "Must be at least 1"),
    offset: z.coerce.number().int().min(0).optional(),
  }),
  replaceValues: z.object({
    column: z.string().min(1, "Column is required"),
    to_replace: z.string(),
    value: z.string(),
    regex: z.boolean().optional(),
  }),
  stringTransform: z
    .object({
      column: z.string().min(1, "Column is required"),
      operation: z.enum(stringOperations),
      find: z.string().optional(),
      replace_with: z.string().optional(),
      width: z.coerce.number().int().min(1).optional(),
      fill_char: z.string().optional(),
      side: z.enum(["left", "right"]).optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.operation === "replace" && !cfg.find) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["find"],
          message: "Text to find is required",
        });
      }
      if (cfg.operation === "pad" && !cfg.width) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["width"],
          message: "Target width is required",
        });
      }
    }),
  calculatedColumn: z.object({
    column_name: z.string().min(1, "Column name is required"),
    expression: z.string().min(1, "Expression is required"),
  }),
  groupByAggregate: z.object({
    group_by: stringArray.min(1, "Add at least one group-by column"),
    aggregations: z.record(z.string(), z.string()),
  }),
  join: z
    .object({
      on: z.union([z.string(), stringArray]).optional(),
      left_on: stringArray.optional(),
      right_on: stringArray.optional(),
      how: z.enum(joinHows),
      suffixes: z.array(z.string()).length(2).optional(),
    })
    .superRefine((cfg, ctx) => {
      const hasOn = Array.isArray(cfg.on) ? cfg.on.length > 0 : !!cfg.on;
      const hasSplit = !!cfg.left_on?.length && !!cfg.right_on?.length;
      if (!hasOn && !hasSplit) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["on"],
          message: "Provide a join key (or both left & right keys)",
        });
      }
    }),
  concatRows: z.object({}),

  // ----- New transform nodes -----
  sampleRows: z
    .object({
      n: z.coerce.number().int().min(1).optional(),
      frac: z.coerce.number().gt(0).max(1).optional(),
      seed: z.coerce.number().int().optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.n == null && cfg.frac == null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["n"],
          message: "Set a row count or a fraction",
        });
      }
    }),
  removeOutliers: z.object({
    columns: stringArray.min(1, "Add at least one column"),
    method: z.enum(outlierMethods),
    action: z.enum(outlierActions),
    factor: z.coerce.number().gt(0).optional(),
    threshold: z.coerce.number().gt(0).optional(),
    lower: z.coerce.number().min(0).max(100).optional(),
    upper: z.coerce.number().min(0).max(100).optional(),
  }),
  roundNumbers: z.object({
    columns: stringArray.min(1, "Add at least one column"),
    decimals: z.coerce.number().int().min(0),
  }),
  binColumn: z.object({
    column: z.string().min(1, "Column is required"),
    new_column: z.string().min(1, "New column name is required"),
    method: z.enum(binMethods),
    bins: z.coerce.number().int().min(2, "At least 2 bins"),
  }),
  extractDateParts: z.object({
    column: z.string().min(1, "Column is required"),
    parts: z.array(z.enum(dateParts)).min(1, "Pick at least one part"),
  }),
  unpivot: z.object({
    id_vars: stringArray.min(1, "Keep at least one identifier column"),
    value_vars: stringArray.optional(),
    var_name: z.string().optional(),
    value_name: z.string().optional(),
  }),
  pivot: z.object({
    index: stringArray.min(1, "Add at least one index column"),
    columns: z.string().min(1, "Column is required"),
    values: z.string().min(1, "Values column is required"),
    aggfunc: z.enum(aggFunctions),
  }),
  splitColumn: z
    .object({
      column: z.string().min(1, "Column is required"),
      mode: z.enum(splitModes),
      delimiter: z.string().optional(),
      pattern: z.string().optional(),
      into: stringArray.min(1, "Name at least one output column"),
      keep_original: z.boolean().optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.mode === "delimiter" && !cfg.delimiter) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["delimiter"],
          message: "A delimiter is required",
        });
      }
      if (cfg.mode === "regex" && !cfg.pattern) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["pattern"],
          message: "A regex pattern is required",
        });
      }
    }),
  parseDates: z.object({
    columns: stringArray.min(1, "Add at least one column"),
    format: z.string().optional(),
    errors: z.enum(["raise", "coerce"]).optional(),
  }),
  mapValues: z
    .object({
      column: z.string().min(1, "Column is required"),
      new_column: z.string().optional(),
      mapping: z.record(z.string(), z.string()),
      default: z.string().optional(),
      use_default: z.boolean().optional(),
    })
    .superRefine((cfg, ctx) => {
      if (!cfg.mapping || Object.keys(cfg.mapping).length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["mapping"],
          message: "Add at least one value mapping",
        });
      }
    }),
  windowFunction: z
    .object({
      function: z.enum(windowFunctions),
      partition_by: stringArray.optional(),
      order_by: stringArray.optional(),
      target: z.string().optional(),
      offset: z.coerce.number().int().min(1).optional(),
      descending: z.boolean().optional(),
      new_column: z.string().min(1, "New column name is required"),
    })
    .superRefine((cfg, ctx) => {
      if (windowTargetFuncs.has(cfg.function) && !cfg.target) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["target"],
          message: "This function needs a target column",
        });
      }
      if (windowRankFuncs.has(cfg.function) && !cfg.order_by?.length) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["order_by"],
          message: "Ranking needs an order-by column",
        });
      }
    }),
  conditionalColumn: z.object({
    new_column: z.string().min(1, "New column name is required"),
    default: z.string().optional(),
    rules: z
      .array(
        z
          .object({
            // New shape: conditions combined by `match` (all = AND, any = OR).
            match: z.enum(["all", "any"]).optional(),
            conditions: z.array(conditionSchema).optional(),
            // Legacy flat shape (one condition stored on the rule itself).
            column: z.string().optional(),
            operator: z.enum(conditionOperators).optional(),
            value: z.union([z.string(), z.number()]).optional(),
            result: z.string().optional(),
          })
          .superRefine((rule, ctx) => {
            const hasConditions =
              Array.isArray(rule.conditions) && rule.conditions.length > 0;
            const hasLegacy = typeof rule.column === "string" && rule.column.length > 0;
            if (!hasConditions && !hasLegacy) {
              ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["conditions"],
                message: "Add at least one condition",
              });
            }
          }),
      )
      .min(1, "Add at least one rule"),
  }),

  sqlInput: z
    .object({
      connection_id: z.string().min(1, "Select a connection"),
      mode: z.enum(["table", "query"]).optional(),
      table: z.string().optional(),
      schema: z.string().nullable().optional(),
      query: z.string().optional(),
    })
    .superRefine((cfg, ctx) => {
      if ((cfg.mode ?? "table") === "query") {
        if (!cfg.query?.trim()) {
          ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["query"], message: "Enter a SQL query" });
        }
      } else if (!cfg.table) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["table"], message: "Select a table" });
      }
    }),
  sqlOutput: z.object({
    connection_id: z.string().min(1, "Select a connection"),
    table: z.string().min(1, "Target table is required"),
    schema: z.string().nullable().optional(),
    if_exists: z.enum(["replace", "append", "fail"]).optional(),
  }),

  storageInput: z.object({
    connection_id: z.string().min(1, "Select a storage connection"),
    path: z.string().min(1, "File path is required"),
    format: z.enum(["csv", "excel", "parquet"]),
  }),
  storageOutput: z.object({
    connection_id: z.string().min(1, "Select a storage connection"),
    path: z.string().min(1, "Destination path is required"),
    format: z.enum(["csv", "excel", "parquet"]),
    if_exists: z.enum(["overwrite", "error"]).optional(),
  }),

  csvOutput: z.object({ dataset_name: z.string().min(1, "Dataset name is required") }),
  excelOutput: z.object({ dataset_name: z.string().min(1, "Dataset name is required") }),
  parquetOutput: z.object({ dataset_name: z.string().min(1, "Dataset name is required") }),

  // ----- Machine learning -----
  trainTestSplit: z.object({
    test_size: z.coerce.number().gt(0, "Must be > 0").lt(1, "Must be < 1"),
    stratify_column: z.string().nullable().optional(),
    // Seed is required for reproducibility (matches the backend).
    seed: z.coerce.number().int("Seed must be a whole number"),
  }),
  scaleFeatures: z.object({
    method: z.enum(["standard", "minmax", "robust"]),
    columns: stringArray.min(1, "Pick at least one column"),
  }),
  encodeCategories: z.object({
    method: z.enum(["onehot", "ordinal"]),
    columns: stringArray.min(1, "Pick at least one column"),
    drop_first: z.boolean().optional(),
  }),
  selectFeatures: z
    .object({
      method: z.enum(["variance", "correlation", "kbest"]),
      threshold: z.coerce.number().optional(),
      k: z.coerce.number().int().min(1).optional(),
      target_column: z.string().optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.method === "kbest") {
        if (!cfg.target_column) {
          ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["target_column"], message: "Pick a target column" });
        }
        if (cfg.k == null) {
          ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["k"], message: "Set how many features to keep" });
        }
      }
    }),
  reduceDimensions: z.object({
    method: z.literal("pca"),
    n_components: z.coerce.number().positive("Must be positive"),
    columns: stringArray.optional(),
    prefix: z.string().optional(),
    seed: z.coerce.number().int().optional(),
  }),
  mlTrain: z
    .object({
      model_type: z.enum(ML_MODEL_VALUES),
      target_column: z.string().optional(),
      feature_columns: stringArray.optional(),
      hyperparameters: z.record(z.string(), z.unknown()).optional(),
      cross_validate: z.boolean().optional(),
      cv_folds: z.coerce.number().int().min(2).optional(),
      mlflow_experiment: z.string().optional(),
      seed: z.coerce.number().int("Seed must be a whole number"),
      preprocessing: z.record(z.string(), z.unknown()).optional(),
    })
    .superRefine((cfg, ctx) => {
      if (isSupervisedModel(cfg.model_type)) {
        if (!cfg.target_column) {
          ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["target_column"], message: "Pick a target column" });
        }
        const feats = cfg.feature_columns ?? [];
        if (cfg.target_column && feats.includes(cfg.target_column)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["feature_columns"],
            message: "The target can't also be a feature (data leakage).",
          });
        }
      }
    }),
  mlPredict: z.object({
    model_uri: z.string().optional(),
    output_column: z.string().min(1, "Name the prediction column"),
    output_proba_columns: stringArray.optional(),
    batch_size: z.coerce.number().int().min(1).nullable().optional(),
  }),
  mlEvaluate: z
    .object({
      task_type: z.enum(["classification", "regression", "clustering"]),
      target_column: z.string().optional(),
      prediction_column: z.string().min(1, "Pick the prediction column"),
      proba_columns: stringArray.optional(),
      metrics: stringArray.optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.task_type !== "clustering" && !cfg.target_column) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["target_column"], message: "Pick the true-value column" });
      }
    }),
  featureImportance: z.object({
    top_n: z.coerce.number().int().min(1).nullable().optional(),
  }),

  // ----- Advanced -----
  pythonTransform: z.object({
    script: z.string().min(1, "Script is required"),
  }),

  // ----- Data Quality -----
  assertNotNull: z.object({
    columns: stringArray.optional(),
    mode: z.enum(["error", "warn"]).optional(),
  }),
  assertUnique: z.object({
    columns: stringArray.optional(),
    mode: z.enum(["error", "warn"]).optional(),
  }),
  assertValueRange: z
    .object({
      column: z.string().min(1, "Select a column"),
      min: z.coerce.number().nullable().optional(),
      max: z.coerce.number().nullable().optional(),
      inclusive: z.boolean().optional(),
      mode: z.enum(["error", "warn"]).optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.min == null && cfg.max == null) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["min"], message: "Set at least one of min or max" });
      }
    }),
  assertExpression: z.object({
    expression: z.string().min(1, "Expression is required"),
    mode: z.enum(["error", "warn"]).optional(),
  }),
  assertRowCount: z
    .object({
      min_rows: z.coerce.number().int().nonnegative().nullable().optional(),
      max_rows: z.coerce.number().int().nonnegative().nullable().optional(),
      mode: z.enum(["error", "warn"]).optional(),
    })
    .superRefine((cfg, ctx) => {
      if (cfg.min_rows == null && cfg.max_rows == null) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["min_rows"], message: "Set at least one of min or max rows" });
      }
      if (cfg.min_rows != null && cfg.max_rows != null && cfg.min_rows > cfg.max_rows) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["min_rows"], message: "Min rows must be ≤ max rows" });
      }
    }),
};

export function getConfigSchema(type: string): z.ZodTypeAny {
  return nodeConfigSchemas[type] ?? z.object({}).passthrough();
}

export const flowFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
});
export type FlowFormValues = z.infer<typeof flowFormSchema>;
