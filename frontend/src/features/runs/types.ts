import type { ParameterValues, RunStatus } from "@/lib/types/shared";

export type NodeResultStatus = "success" | "failed" | "skipped";

export interface NodeResult {
  node_id: string;
  type: string;
  label: string;
  status: NodeResultStatus;
  rows: number | null;
  columns: string[];
  sample: Record<string, unknown>[];
  error: string | null;
  // ML-specific — null for non-ML nodes.
  ml_metrics?: Record<string, number> | null;
  mlflow_run_id?: string | null;
  model_uri?: string | null;
  task_type?: string | null;
  cv_scores?: number[] | null;
  // Assertion node fields — null for non-assertion nodes.
  assertion_passed?: boolean | null;
  assertion_violation_count?: number | null;
  assertion_violating_sample?: Record<string, unknown>[] | null;
  // Chart node artifact — null for non-chart nodes.
  chart?: ChartArtifact | null;
}

// ---- Chart-node artifacts (stored on the run by the backend chart nodes) ----

export interface ChartCategoryDatum {
  label: string;
  value: number | null;
}

export interface BoxGroupStats {
  label: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number;
  count: number;
}

/** Render-ready chart data computed by a chart node over the full run data.
 *  Shapes mirror backend/app/engine/transformations/charts.py. */
export interface ChartArtifact {
  kind: "bar" | "line" | "area" | "scatter" | "pie" | "histogram" | "boxplot" | "heatmap";
  rows_seen?: number;
  /** Optional user-set chart title (falls back to the node label). */
  title?: string;
  // bar / pie / histogram
  data?: ChartCategoryDatum[];
  x?: string;
  y?: string | null;
  aggregate?: string;
  orientation?: "vertical" | "horizontal";
  category?: string;
  value?: string | null;
  column?: string;
  bins?: number;
  total_categories?: number;
  // stacked bar / line / area
  rows?: Array<Record<string, string | number | null>>;
  series?: string[];
  group_by?: string | null;
  total_series?: number;
  total_points?: number;
  // scatter
  points?: Array<[number | null, number | null]>;
  // boxplot
  groups?: BoxGroupStats[];
  total_groups?: number;
  // heatmap
  columns?: string[];
  matrix?: Array<Array<number | null>>;
  total_columns?: number;
  /** Explicitly chosen heatmap columns that weren't numeric/varying enough. */
  dropped_columns?: string[];
}

/** One input dataset a run resolved, with the concrete version it read. */
export interface InputDatasetRef {
  dataset_id: string;
  version_number: number | null;
  // Snapshotted at run time; null for runs recorded before this field existed
  // or when the dataset had no name to resolve. Falls back to a live lookup.
  dataset_name: string | null;
}

export interface FlowRun {
  id: string;
  flow_id: string;
  input_dataset_id: string | null;
  /** Every input the run resolved (join/concat flows have more than one). */
  input_datasets: InputDatasetRef[] | null;
  status: RunStatus;
  output_location: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  logs_json: unknown;
  node_results: NodeResult[] | null;
  /** Resolved flow-parameter values this run executed with (null if none). */
  parameters: ParameterValues | null;
  created_at: string;
}

/** How a run was triggered: a manual click or the background scheduler. */
export type RunTrigger = "manual" | "schedule";

/** Lightweight run row for the history list (no per-node samples). */
export interface FlowRunSummary {
  id: string;
  flow_id: string;
  flow_name: string | null;
  project_id: string | null;
  input_dataset_id: string | null;
  input_datasets: InputDatasetRef[] | null;
  status: RunStatus;
  engine: string;
  trigger: RunTrigger;
  schedule_id: string | null;
  output_location: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RunListFilters {
  flow_id?: string;
  project_id?: string;
  dataset_id?: string;
  schedule_id?: string;
  status?: RunStatus;
  started_after?: string;
  started_before?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
