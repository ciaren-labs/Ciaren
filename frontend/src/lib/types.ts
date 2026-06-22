// Shared domain types mirroring the FlowFrame backend REST API.

export interface DatasetSchemaField {
  name: string;
  type: string;
}

export type DatasetSourceType = "csv" | "excel" | "parquet";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  /** Brand-palette accent key (e.g. "violet") for the project card. */
  color: string;
  is_default: boolean;
  dataset_count: number;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  color?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  color?: string;
}

export interface Dataset {
  id: string;
  name: string;
  source_type: DatasetSourceType;
  project_id: string | null;
  /** Highest version number available (latest snapshot). */
  latest_version: number;
  /** Total number of versions uploaded under this name. */
  version_count: number;
  // The backend exposes these under aliased names (column_schema / data_sample);
  // `location` is intentionally never sent to the client. They reflect the latest version.
  column_schema: DatasetSchemaField[] | null;
  data_sample: Record<string, unknown>[] | null;
  created_at: string;
  updated_at: string;
}

export interface DatasetVersion {
  id: string;
  version_number: number;
  row_count: number;
  column_schema: DatasetSchemaField[] | null;
  created_at: string;
}

export type RunStatus = "pending" | "running" | "success" | "failed";

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
}

export interface FlowRun {
  id: string;
  flow_id: string;
  input_dataset_id: string | null;
  status: RunStatus;
  output_location: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  logs_json: unknown;
  node_results: NodeResult[] | null;
  created_at: string;
}

/** Lightweight run row for the history list (no per-node samples). */
export interface FlowRunSummary {
  id: string;
  flow_id: string;
  flow_name: string | null;
  project_id: string | null;
  input_dataset_id: string | null;
  status: RunStatus;
  output_location: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RunListFilters {
  flow_id?: string;
  project_id?: string;
  dataset_id?: string;
  status?: RunStatus;
  started_after?: string;
  started_before?: string;
  limit?: number;
}

// React Flow compatible graph stored in flow.graph_json.
export interface GraphNodeData {
  label: string;
  config: Record<string, unknown>;
  [key: string]: unknown;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: GraphNodeData;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface GraphJson {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Flow {
  id: string;
  name: string;
  description: string | null;
  project_id: string | null;
  graph_json: GraphJson | null;
  created_at: string;
  updated_at: string;
}

export interface FlowCreate {
  name: string;
  description?: string;
  project_id?: string;
  graph_json: GraphJson;
}

export interface FlowUpdate {
  name?: string;
  description?: string;
  project_id?: string;
  graph_json?: GraphJson;
}

export interface PreviewResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
}

export interface FlowPreviewRequest {
  node_id?: string;
  limit?: number;
}

export interface TransformationPreviewRequest {
  type: string;
  dataset_id: string;
  config: Record<string, unknown>;
  limit?: number;
}

export interface ExportCodeResponse {
  code: string;
}
