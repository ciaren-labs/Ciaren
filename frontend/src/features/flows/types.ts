import type { ConfigSchema, ParameterSpec, ParameterValues } from "@/lib/types/shared";

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
  /** Engine persisted with the graph so the editor restores the last choice. */
  engine?: "pandas" | "polars";
  /** Parameters declared on the flow (referenced by node configs via {{ name }}). */
  parameters?: ParameterSpec[];
}

export interface Flow {
  id: string;
  name: string;
  description: string | null;
  project_id: string | null;
  graph_json: GraphJson | null;
  is_disabled: boolean;
  created_at: string;
  updated_at: string;
  /** When this flow last ran (any trigger), or null if it never has. */
  last_run_at: string | null;
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
  is_disabled?: boolean;
}

export interface FlowPreviewRequest {
  node_id?: string;
  limit?: number;
  profile?: boolean;
  /** Flow-parameter overrides so the preview reflects the values a run would use. */
  parameters?: ParameterValues | null;
}

/** Portable, environment-independent description of a flow (name + node graph). */
export interface FlowDocument {
  format: string;
  name: string;
  description?: string | null;
  graph_json: Record<string, unknown>;
}

/** Import payload: accepts either envelope — the legacy `graph_json` shape
 * (today's real export format) or the versioned `graph`/`schemaVersion`
 * shape — at least one of `graph_json`/`graph` is required. */
export interface FlowImport {
  format?: string;
  name?: string;
  description?: string | null;
  project_id?: string;
  graph_json?: Record<string, unknown>;
  graph?: Record<string, unknown>;
  schemaVersion?: string;
}

/** Response from the standalone, non-persisting flow-document migration
 * utility (`POST /flows/migrate-document`). */
export interface FlowMigrateDocumentResponse {
  document: Record<string, unknown>;
  migrated: boolean;
  from_version: string;
  to_version: string;
}

export interface ExportCodeResponse {
  /** pandas script (kept as `code` for back-compat). */
  code: string;
  /** eager polars equivalent. */
  polars: string;
  /** optimized lazy polars (`scan_*` → `collect()`) equivalent. */
  polars_lazy: string;
  /** importable JSON description of the flow. */
  flow_document: FlowDocument;
}

// ---- Catalog (backend-fed node metadata) -----------------------------------
// Mirrors app/plugin_api NodeSpec/PortSpec, served by GET /api/catalog/nodes.

export type CatalogPortKind = "dataframe" | "model";

export interface CatalogPort {
  id: string;
  type: CatalogPortKind;
  required: boolean;
  multi: boolean;
}

export interface CatalogNode {
  id: string;
  label: string;
  category: string;
  description: string;
  provider: string;
  version: string;
  inputs: CatalogPort[];
  outputs: CatalogPort[];
  default_config: Record<string, unknown>;
  capabilities: string[];
  permissions: string[];
  requires_ml: boolean;
  is_model_sink: boolean;
  is_flow_terminal?: boolean;
  config_schema: ConfigSchema;
}
