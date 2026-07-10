import { request } from "@/lib/api/client";
import type {
  MlExperiment,
  MlExperimentRun,
  MlExperimentSummary,
  MlModelCatalogItem,
  MlNodeMetrics,
  MlRegisteredModel,
  MlRegisterResult,
} from "./types";

export const mlApi = {
  metrics: (runId: string) => request<MlNodeMetrics[]>(`/runs/${runId}/ml/metrics`),
  register: (runId: string, body: { model_name: string; stage?: string | null }) =>
    request<MlRegisterResult>(`/runs/${runId}/ml/register`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  experiments: (flowId: string) => request<MlExperiment[]>(`/flows/${flowId}/ml/experiments`),
  // ML Models page: registry + experiment leaderboard (server-wide, not per-flow).
  registeredModels: () => request<MlRegisteredModel[]>(`/ml/models`),
  modelCatalog: () => request<MlModelCatalogItem[]>(`/ml/model-catalog`),
  allExperiments: () => request<MlExperimentSummary[]>(`/ml/experiments`),
  experimentRuns: (experimentId: string) =>
    request<MlExperimentRun[]>(`/ml/experiments/${experimentId}/runs`),
  setAlias: (modelName: string, alias: string, version: string) =>
    request<{ model_name: string; alias: string; version: string }>(
      `/ml/models/${encodeURIComponent(modelName)}/alias`,
      { method: "POST", body: JSON.stringify({ alias, version }) },
    ),
  clearAlias: (modelName: string, alias: string) =>
    request<{ model_name: string; alias: string; cleared: boolean }>(
      `/ml/models/${encodeURIComponent(modelName)}/alias/${encodeURIComponent(alias)}`,
      { method: "DELETE" },
    ),
};
