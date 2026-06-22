// Catalog of all supported node types, their categories, default config, and
// handle topology. This is the single source of truth the UI uses to render
// the node palette, default new-node config, and edge-handle expectations.

export type NodeCategory = "input" | "clean" | "transform" | "output";

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
  // ----- Cleaning / single-input transforms -----
  {
    type: "dropNulls",
    label: "Drop Nulls",
    category: "clean",
    defaultConfig: { subset: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Drop rows containing null values.",
  },
  {
    type: "fillNulls",
    label: "Fill Nulls",
    category: "clean",
    defaultConfig: { value: "", columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Replace null values with a fixed value.",
  },
  {
    type: "dropColumns",
    label: "Drop Columns",
    category: "clean",
    defaultConfig: { columns: [] },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Remove columns from the dataframe.",
  },
  {
    type: "renameColumns",
    label: "Rename Columns",
    category: "clean",
    defaultConfig: { mapping: {} },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Rename columns using an old -> new mapping.",
  },
  {
    type: "selectColumns",
    label: "Select Columns",
    category: "clean",
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
    defaultConfig: { columns: [], ascending: true },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Sort rows by one or more columns.",
  },
  {
    type: "castDtypes",
    label: "Change Types",
    category: "clean",
    defaultConfig: { casts: {} },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Cast columns to a new data type.",
  },
  {
    type: "limitRows",
    label: "Limit Rows",
    category: "clean",
    defaultConfig: { n: 100 },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Keep only the first N rows.",
  },
  {
    type: "replaceValues",
    label: "Replace Values",
    category: "clean",
    defaultConfig: { column: "", to_replace: "", value: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Replace values in a column.",
  },
  {
    type: "stringTransform",
    label: "String Transform",
    category: "clean",
    defaultConfig: { column: "", operation: "lower" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Apply a string operation to a column.",
  },
  {
    type: "calculatedColumn",
    label: "Calculated Column",
    category: "transform",
    defaultConfig: { column_name: "", expression: "" },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Create a new column from an expression.",
  },
  {
    type: "groupByAggregate",
    label: "Group By Aggregate",
    category: "transform",
    defaultConfig: { group_by: [], aggregations: {} },
    inputHandles: ["in"],
    hasOutput: true,
    description: "Group rows and aggregate columns.",
  },
  // ----- Multi-input transforms -----
  {
    type: "join",
    label: "Join / Merge",
    category: "transform",
    defaultConfig: { on: "", how: "inner" },
    inputHandles: ["left", "right"],
    hasOutput: true,
    description: "Join two dataframes (left + right inputs).",
  },
  {
    type: "concatRows",
    label: "Concat Rows",
    category: "transform",
    defaultConfig: {},
    inputHandles: ["in"],
    multiInput: true,
    hasOutput: true,
    description: "Stack multiple dataframes vertically.",
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
  transform: "Transform",
  output: "Outputs",
};

export const CATEGORY_ORDER: NodeCategory[] = [
  "input",
  "clean",
  "transform",
  "output",
];
