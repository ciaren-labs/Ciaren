// Catalog of all supported node types, their categories, default config, and
// handle topology. This is the single source of truth the UI uses to render
// the node palette, default new-node config, and edge-handle expectations.

export type NodeCategory =
  | "input"
  | "clean"
  | "columns"
  | "reshape"
  | "analytics"
  | "quality"
  | "ml"
  | "output";

export interface NodeTypeDef {
  type: string;
  label: string;
  category: NodeCategory;
  /** Default config object for a freshly-created node. */
  defaultConfig: Record<string, unknown>;
  /** Input handle ids. Empty for input nodes. */
  inputHandles: string[];
  /** Input handles that may be connected but aren't required (e.g. mlPredict's
   *  "model" handle, optional when a model_uri is set in config). */
  optionalInputHandles?: string[];
  /** Whether the node accepts an arbitrary number of incoming edges. */
  multiInput?: boolean;
  /** Output handle ids. Empty for output nodes (they still flow downstream).
   *  Single-output nodes omit this and use the implicit "out" handle. */
  outputHandles?: string[];
  /** Input handles that carry a trained model rather than a dataframe. A model
   *  handle may only connect to another model handle (enforced by the backend),
   *  and the editor renders it distinctly. */
  modelInputHandles?: string[];
  /** Output handles that emit a trained model rather than a dataframe. */
  modelOutputHandles?: string[];
  /** Whether the node emits anything downstream (renders a source handle). */
  hasOutput: boolean;
  /** A terminal that persists a result without a file-output node (mlTrain logs a
   *  model to MLflow), so a flow ending here is still "complete". */
  isModelSink?: boolean;
  /** Only available when the ML extension is installed + enabled on the server. */
  requiresMl?: boolean;
  description: string;
}

export const NODE_TYPES: NodeTypeDef[] = [
  // ----- Inputs -----
  {
    type: "csvInput",
    label: "CSV Input",
    category: "input",
    defaultConfig: { dataset_id: "", dataset_version: null },
    inputHandles: [],
    hasOutput: true,
    description: "Load rows from an uploaded CSV dataset.",
  },
  {
    type: "excelInput",
    label: "Excel Input",
    category: "input",
    defaultConfig: { dataset_id: "", dataset_version: null },
    inputHandles: [],
    hasOutput: true,
    description: "Load rows from an uploaded Excel dataset.",
  },
  {
    type: "parquetInput",
    label: "Parquet Input",
    category: "input",
    defaultConfig: { dataset_id: "", dataset_version: null },
    inputHandles: [],
    hasOutput: true,
    description: "Load rows from an uploaded Parquet dataset.",
  },
  {
    type: "jsonInput",
    label: "JSON Input",
    category: "input",
    defaultConfig: { dataset_id: "", dataset_version: null },
    inputHandles: [],
    hasOutput: true,
    description: "Load records from an uploaded JSON dataset.",
  },
  {
    type: "textInput",
    label: "Text Input",
    category: "input",
    defaultConfig: { dataset_id: "", dataset_version: null },
    inputHandles: [],
    hasOutput: true,
    description: "Load lines from an uploaded text file (one row per line).",
  },
  {
    type: "sqlInput",
    label: "SQL Input",
    category: "input",
    defaultConfig: { connection_id: "", mode: "table", table: "", schema: null, query: "" },
    inputHandles: [],
    hasOutput: true,
    description: "Read rows live from a database table or query.",
  },
  {
    type: "storageInput",
    label: "Storage Input",
    category: "input",
    defaultConfig: { connection_id: "", path: "", format: "csv" },
    inputHandles: [],
    hasOutput: true,
    description: "Read a file (CSV, Excel, Parquet) from S3, Azure Blob, GCS, or a local folder.",
  },
  // ----- Cleaning / single-input transforms -----
  {
    type: "dropNulls",
    label: "Drop Nulls",
    category: "clean",
    defaultConfig: { subset: [], how: "any" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Drop rows containing null values.",
  },
  {
    type: "fillNulls",
    label: "Fill Nulls",
    category: "clean",
    defaultConfig: { strategy: "constant", value: "", columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Replace null values with a fixed value.",
  },
  {
    type: "dropColumns",
    label: "Drop Columns",
    category: "columns",
    defaultConfig: { columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Remove columns from the dataframe.",
  },
  {
    type: "renameColumns",
    label: "Rename Columns",
    category: "columns",
    defaultConfig: { mapping: {} },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Rename columns using an old -> new mapping.",
  },
  {
    type: "selectColumns",
    label: "Select Columns",
    category: "columns",
    defaultConfig: { columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Keep only the selected columns.",
  },
  {
    type: "removeDuplicates",
    label: "Remove Duplicates",
    category: "clean",
    defaultConfig: { subset: [], keep: "first" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Drop duplicate rows.",
  },
  {
    type: "filterRows",
    label: "Filter Rows",
    category: "clean",
    defaultConfig: { column: "", operator: "==", value: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Keep rows matching a condition.",
  },
  {
    type: "sortRows",
    label: "Sort Rows",
    category: "clean",
    defaultConfig: { columns: [], ascending: true, na_position: "last" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Sort rows by one or more columns.",
  },
  {
    type: "castDtypes",
    label: "Change Types",
    category: "clean",
    defaultConfig: { casts: {}, errors: "raise", format: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Cast columns to a new data type.",
  },
  {
    type: "limitRows",
    label: "Limit Rows",
    category: "clean",
    defaultConfig: { n: 100, offset: 0 },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Keep only the first N rows.",
  },
  {
    type: "replaceValues",
    label: "Replace Values",
    category: "columns",
    defaultConfig: { column: "", to_replace: "", value: "", regex: false },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Replace values in a column.",
  },
  {
    type: "stringTransform",
    label: "String Transform",
    category: "columns",
    defaultConfig: { column: "", operation: "lower" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Apply a string operation to a column.",
  },
  {
    type: "calculatedColumn",
    label: "Calculated Column",
    category: "columns",
    defaultConfig: { column_name: "", expression: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Create a new column from an expression.",
  },
  {
    type: "groupByAggregate",
    label: "Group By Aggregate",
    category: "reshape",
    defaultConfig: { group_by: [], aggregations: {} },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Group rows and aggregate columns.",
  },
  // ----- Multi-input transforms -----
  {
    type: "join",
    label: "Join / Merge",
    category: "reshape",
    defaultConfig: { on: "", how: "inner" },
    inputHandles: ["left", "right"],
    hasOutput: true,
    description: "Join two dataframes (left + right inputs).",
  },
  {
    type: "concatRows",
    label: "Concat Rows",
    category: "reshape",
    defaultConfig: {},
    inputHandles: ["in"],
    multiInput: true,
    hasOutput: true,
    description: "Stack multiple dataframes vertically.",
  },
  // ----- New cleaning / shaping nodes -----
  {
    type: "sampleRows",
    label: "Sample Rows",
    category: "clean",
    defaultConfig: { n: 100, seed: null },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Take a random sample of rows.",
  },
  {
    type: "removeOutliers",
    label: "Remove Outliers",
    category: "analytics",
    defaultConfig: {
      columns: [],
      method: "iqr",
      action: "drop",
      factor: 1.5,
      threshold: 3,
      lower: 1,
      upper: 99,
    },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Drop or clip statistical outliers (IQR / z-score / percentile).",
  },
  {
    type: "roundNumbers",
    label: "Round Numbers",
    category: "analytics",
    defaultConfig: { columns: [], decimals: 0 },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Round numeric columns to a number of decimals.",
  },
  {
    type: "binColumn",
    label: "Bin Column",
    category: "analytics",
    defaultConfig: { column: "", new_column: "", method: "equalwidth", bins: 4 },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Bucket a numeric column into bins (equal-width or quantile).",
  },
  {
    type: "extractDateParts",
    label: "Extract Date Parts",
    category: "analytics",
    defaultConfig: { column: "", parts: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Add year/month/day/weekday/hour columns from a date column.",
  },
  {
    type: "unpivot",
    label: "Unpivot / Melt",
    category: "reshape",
    defaultConfig: { id_vars: [], value_vars: [], var_name: "variable", value_name: "value" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Reshape wide columns into long key/value rows.",
  },
  {
    type: "pivot",
    label: "Pivot Table",
    category: "reshape",
    defaultConfig: { index: [], columns: "", values: "", aggfunc: "sum" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Reshape long rows into a wide aggregated table.",
  },
  {
    type: "splitColumn",
    label: "Split Column",
    category: "columns",
    defaultConfig: {
      column: "",
      mode: "delimiter",
      delimiter: ",",
      pattern: "",
      into: [],
      keep_original: true,
    },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Split a text column into several columns by a delimiter or regex groups.",
  },
  {
    type: "parseDates",
    label: "Parse Dates",
    category: "analytics",
    defaultConfig: { columns: [], format: "", errors: "coerce" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Parse text columns into datetimes (optional format, coerce errors).",
  },
  {
    type: "mapValues",
    label: "Map Values",
    category: "columns",
    defaultConfig: {
      column: "",
      new_column: "",
      mapping: {},
      default: "",
      use_default: false,
    },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Map column values via a lookup (CASE-WHEN), with an optional default.",
  },
  {
    type: "windowFunction",
    label: "Window Function",
    category: "analytics",
    defaultConfig: {
      function: "row_number",
      partition_by: [],
      order_by: [],
      target: "",
      offset: 1,
      descending: false,
      new_column: "",
    },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Rank, running total, or lag/lead over a partition and order.",
  },
  {
    type: "conditionalColumn",
    label: "Conditional Column",
    category: "analytics",
    defaultConfig: { new_column: "", default: "", rules: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Build a column from if/elif/else rules (CASE-WHEN).",
  },
  // ----- Advanced -----
  {
    type: "pythonTransform",
    label: "Python Transform",
    category: "analytics",
    defaultConfig: { script: "# Write the body of: def transform(df):\n#   ...\nreturn df" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Run arbitrary Python code on the DataFrame — an escape hatch for custom logic.",
  },
  // ----- Data Quality -----
  {
    type: "assertNotNull",
    label: "Assert Not Null",
    category: "quality",
    defaultConfig: { columns: [], mode: "error" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Fail or warn when any specified column contains null values.",
  },
  {
    type: "assertUnique",
    label: "Assert Unique",
    category: "quality",
    defaultConfig: { columns: [], mode: "error" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Fail or warn when duplicate rows exist across the specified columns.",
  },
  {
    type: "assertValueRange",
    label: "Assert Value Range",
    category: "quality",
    defaultConfig: { column: "", min: null, max: null, inclusive: true, mode: "error" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Fail or warn when column values fall outside a numeric range.",
  },
  {
    type: "assertExpression",
    label: "Assert Expression",
    category: "quality",
    defaultConfig: { expression: "", mode: "error" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Fail or warn when a boolean expression is false for any row.",
  },
  {
    type: "assertRowCount",
    label: "Assert Row Count",
    category: "quality",
    defaultConfig: { min_rows: null, max_rows: null, mode: "error" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Fail or warn when the row count falls outside declared bounds.",
  },
  // ----- Machine Learning -----
  {
    type: "trainTestSplit",
    label: "Train / Test Split",
    category: "ml",
    requiresMl: true,
    defaultConfig: { test_size: 0.2, stratify_column: null, seed: 42 },
    inputHandles: ["in"],
    outputHandles: ["train", "test"],
    hasOutput: true,
    description: "Split rows into a training set and a test set (seed required).",
  },
  {
    type: "scaleFeatures",
    label: "Scale Features",
    category: "ml",
    requiresMl: true,
    defaultConfig: { method: "standard", columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Standardize / normalize numeric columns (standard, min-max, robust).",
  },
  {
    type: "encodeCategories",
    label: "Encode Categories",
    category: "ml",
    requiresMl: true,
    defaultConfig: { method: "onehot", columns: [], drop_first: false },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Turn categorical columns into numbers (one-hot or ordinal).",
  },
  {
    type: "selectFeatures",
    label: "Select Features",
    category: "ml",
    requiresMl: true,
    defaultConfig: { method: "variance", threshold: 0.0, k: 10, target_column: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Keep the most useful features (variance, correlation, or top-K).",
  },
  {
    type: "reduceDimensions",
    label: "Reduce Dimensions",
    category: "ml",
    requiresMl: true,
    defaultConfig: { method: "pca", n_components: 2, columns: [], prefix: "pc", seed: 42 },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Compress numeric features into principal components (PCA).",
  },
  {
    type: "mlTrain",
    label: "Train Model",
    category: "ml",
    requiresMl: true,
    defaultConfig: {
      model_type: "random_forest_classifier",
      target_column: "",
      feature_columns: [],
      hyperparameters: {},
      cross_validate: false,
      cv_folds: 5,
      seed: 42,
    },
    inputHandles: ["in"],
    outputHandles: ["model"],
    modelOutputHandles: ["model"],
    hasOutput: true,
    isModelSink: true,
    description: "Fit a model and log it to MLflow (classification, regression, clustering).",
  },
  {
    type: "mlPredict",
    label: "Predict",
    category: "ml",
    requiresMl: true,
    defaultConfig: { model_uri: "", output_column: "prediction", output_proba_columns: [], batch_size: null },
    inputHandles: ["in"],
    optionalInputHandles: ["model"],
    modelInputHandles: ["model"],
    hasOutput: true,
    description: "Score rows with a trained model (from the model wire or a registry URI).",
  },
  {
    type: "mlEvaluate",
    label: "Evaluate",
    category: "ml",
    requiresMl: true,
    defaultConfig: {
      task_type: "classification",
      target_column: "",
      prediction_column: "prediction",
      proba_columns: [],
      metrics: [],
    },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Compute metrics from predictions (accuracy, RMSE, silhouette, …).",
  },
  {
    type: "featureImportance",
    label: "Feature Importance",
    category: "ml",
    requiresMl: true,
    defaultConfig: { top_n: null },
    inputHandles: ["model"],
    modelInputHandles: ["model"],
    hasOutput: true,
    description: "Rank which features a trained model relied on most.",
  },
  // ----- Outputs -----
  {
    type: "csvOutput",
    label: "CSV Output",
    category: "output",
    defaultConfig: { path: "" },
    inputHandles: ["in"],
    hasOutput: false,
    description: "Write the result to a CSV file.",
  },
  {
    type: "excelOutput",
    label: "Excel Output",
    category: "output",
    defaultConfig: { path: "" },
    inputHandles: ["in"],
    hasOutput: false,
    description: "Write the result to an Excel file.",
  },
  {
    type: "parquetOutput",
    label: "Parquet Output",
    category: "output",
    defaultConfig: { path: "" },
    inputHandles: ["in"],
    hasOutput: false,
    description: "Write the result to a Parquet file.",
  },
  {
    type: "sqlOutput",
    label: "SQL Output",
    category: "output",
    defaultConfig: { connection_id: "", table: "", schema: null, if_exists: "replace" },
    inputHandles: ["in"],
    hasOutput: false,
    description: "Write the result to a database table.",
  },
  {
    type: "storageOutput",
    label: "Storage Output",
    category: "output",
    defaultConfig: { connection_id: "", path: "", format: "parquet", if_exists: "overwrite" },
    inputHandles: ["in"],
    hasOutput: false,
    description: "Write the result as a file (CSV, Excel, Parquet) to S3, Azure Blob, GCS, or a local folder.",
  },
];

export const NODE_TYPE_MAP: Record<string, NodeTypeDef> = Object.fromEntries(
  NODE_TYPES.map((n) => [n.type, n]),
);

export function getNodeTypeDef(type: string): NodeTypeDef | undefined {
  return NODE_TYPE_MAP[type];
}

export const CATEGORY_LABELS: Record<NodeCategory, string> = {
  input: "Inputs",
  clean: "Cleaning",
  columns: "Columns",
  reshape: "Reshape",
  analytics: "Analytics",
  quality: "Data Quality",
  ml: "Machine Learning",
  output: "Outputs",
};

export const CATEGORY_ORDER: NodeCategory[] = [
  "input",
  "clean",
  "columns",
  "reshape",
  "analytics",
  "quality",
  "ml",
  "output",
];

/** Output handle ids for a node (single implicit "out" unless it declares more). */
export function getOutputHandles(def: NodeTypeDef): string[] {
  if (def.outputHandles) return def.outputHandles;
  return def.hasOutput ? ["out"] : [];
}

/** Whether an output handle carries a trained model rather than a dataframe.
 *  For a single-output model node (mlTrain) the edge has no sourceHandle, so it
 *  resolves to the node's sole output handle. */
export function isModelOutputHandle(
  def: NodeTypeDef,
  handle: string | null | undefined,
): boolean {
  const handles = def.modelOutputHandles;
  if (!handles || handles.length === 0) return false;
  const resolved = handle ?? getOutputHandles(def)[0];
  return resolved != null && handles.includes(resolved);
}

/** Whether an input handle expects a trained model rather than a dataframe. */
export function isModelInputHandle(
  def: NodeTypeDef,
  handle: string | null | undefined,
): boolean {
  const handles = def.modelInputHandles;
  if (!handles || handles.length === 0) return false;
  return handles.includes(handle ?? "in");
}
