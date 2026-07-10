import type { ConfigSchema } from "@/lib/types/shared";

/** Per-node ML results returned by GET /runs/{id}/ml/metrics. */
export interface MlNodeMetrics {
  node_id: string;
  type: string;
  label: string | null;
  ml_metrics: Record<string, number> | null;
  model_uri: string | null;
  task_type: string | null;
  cv_scores: number[] | null;
  mlflow_run_id: string | null;
}

export interface MlExperiment {
  name: string;
  experiment_id: string;
  lifecycle_stage: string;
  artifact_location: string;
}

export interface MlRegisterResult {
  model_name: string;
  version: string | number;
  model_uri: string;
  alias: string | null;
}

// ---- ML Models page (registry + experiments) ------------------------------

export interface MlLineage {
  flow_id?: string;
  run_id?: string;
  dataset_ids?: string[];
}

export interface MlModelVersion {
  version: string;
  run_id: string | null;
  status: string | null;
  aliases: string[];
  created: string | null;
  metrics: Record<string, number>;
  lineage: MlLineage;
}

export interface MlRegisteredModel {
  name: string;
  description: string | null;
  aliases: Record<string, string>;
  last_updated: string | null;
  versions: MlModelVersion[];
}

export interface MlModelCatalogItem {
  model_type: string;
  task: string;
  available: boolean;
  requires: string[];
  missing: string[];
  warning: string | null;
  /** Contributing provider: "ciaren.ml" for built-ins, a plugin id otherwise. */
  provider?: string;
  /** Display label (plugin model types only; built-ins are mirrored statically). */
  label?: string | null;
  supervised?: boolean;
  default_hyperparameters?: Record<string, unknown>;
  hyperparameter_schema?: ConfigSchema;
}

export interface MlExperimentSummary {
  experiment_id: string;
  name: string;
  lifecycle_stage: string;
  last_run: string | null;
}

export interface MlExperimentRun {
  run_id: string;
  run_name: string;
  status: string;
  start_time: string | null;
  metrics: Record<string, number>;
  params: Record<string, string>;
  lineage: MlLineage;
}
