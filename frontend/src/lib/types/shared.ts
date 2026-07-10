// Cross-domain types shared by three or more features. Domain-specific types
// live in each feature's own `types.ts` (e.g. features/datasets/types.ts).

/** Per-column statistics (see backend app/engine/profile.py). Most fields are
 *  type-dependent and only present when relevant to the column's dtype. */
export interface ColumnProfile {
  name: string;
  dtype: "integer" | "float" | "boolean" | "datetime" | "string";
  null_count: number;
  null_pct: number;
  distinct: number;
  scanned: number;
  total: number;
  // numeric
  min?: number | string | null;
  max?: number | string | null;
  mean?: number | null;
  std?: number | null;
  // boolean
  true_count?: number;
  // string
  min_len?: number;
  max_len?: number;
  top_values?: { value: string; count: number }[];
}

/** One field of a schema-driven config form (mirrors app/plugin_api ConfigFieldSpec). */
export interface ConfigField {
  key: string;
  label?: string;
  type?:
    | "string"
    | "number"
    | "integer"
    | "boolean"
    | "select"
    | "string_list"
    | "column"
    | "column_list";
  required?: boolean;
  default?: unknown;
  placeholder?: string;
  help?: string;
  options?: string[];
  min?: number | null;
  max?: number | null;
  secret?: boolean;
}

export interface ConfigSchema {
  fields?: ConfigField[];
}

/** Dataframe engine a run executes on. Mirrors the backend Engine enum. */
export type Engine = "pandas" | "polars";
export const ENGINES: readonly Engine[] = ["pandas", "polars"];

export type RunStatus = "pending" | "running" | "success" | "failed" | "cancelled";

// ---- Flow parameters (referenced by flows, schedules, and preview/run requests) ----

/** Declared type of a flow parameter (mirrors the backend ParameterType enum). */
export type ParameterType = "string" | "integer" | "number" | "boolean";
export const PARAMETER_TYPES: readonly ParameterType[] = [
  "string",
  "integer",
  "number",
  "boolean",
];

/** A parameter declared on a flow, stored in graph_json.parameters. Node configs
 *  reference it via `{{ name }}`; values resolve at run/preview/schedule time. */
export interface ParameterSpec {
  name: string;
  type: ParameterType;
  /** Default value (already typed). Absent/null means the parameter is required. */
  default?: unknown;
  description?: string | null;
}

/** Resolved or override parameter values keyed by name. */
export type ParameterValues = Record<string, unknown>;

export interface PreviewResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  profile: ColumnProfile[] | null;
}
