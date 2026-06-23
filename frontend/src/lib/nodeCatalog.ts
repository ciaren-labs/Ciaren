// Catalog of all supported node types, their categories, default config, and
// handle topology. This is the single source of truth the UI uses to render
// the node palette, default new-node config, and edge-handle expectations.

export type NodeCategory =
  | "input"
  | "clean"
  | "columns"
  | "reshape"
  | "analytics"
  | "output";

export interface NodeTypeDef {
  type: string;
  label: string;
  category: NodeCategory;
  /** Default config object for a freshly-created node. */
  defaultConfig: Record<string, unknown>;
  /** Input handle ids. Empty for input nodes. */
  inputHandles: string[];
  /** Whether the node accepts an arbitrary number of incoming edges. */
  multiInput?: boolean;
  /** Output handle ids. Empty for output nodes (they still flow downstream). */
  hasOutput: boolean;
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
  output: "Outputs",
};

export const CATEGORY_ORDER: NodeCategory[] = [
  "input",
  "clean",
  "columns",
  "reshape",
  "analytics",
  "output",
];
