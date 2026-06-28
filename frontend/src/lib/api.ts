// Centralized, typed API client for the FlowFrame backend.
// All requests go through the Vite dev proxy: /api -> http://localhost:8055

import type {
  CatalogNode,
  ColumnProfile,
  Connection,
  ConnectionCreate,
  ConnectionTestResult,
  ConnectionUpdate,
  Dataset,
  DatasetSchemaField,
  DatasetVersion,
  ExportCodeResponse,
  FlowImport,
  Flow,
  FlowCreate,
  FlowPreviewRequest,
  FlowRun,
  FlowRunSummary,
  FlowUpdate,
  MlExperiment,
  MlExperimentRun,
  MlExperimentSummary,
  MlNodeMetrics,
  MlRegisteredModel,
  MlRegisterResult,
  PluginDiagnostics,
  PluginInfo,
  PreviewResponse,
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProviderInfo,
  RunListFilters,
  Schedule,
  ScheduleCreate,
  ScheduleUpdate,
  TableInfo,
  TransformationPreviewRequest,
} from "./types";

/** Build a `?a=b&c=d` query string from defined values only. */
function queryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  const usp = new URLSearchParams();
  for (const [k, v] of entries) usp.set(k, String(v));
  return `?${usp.toString()}`;
}

const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed with status ${res.status}`;
  let details: unknown;
  try {
    const body = await res.json();
    // Backend may return { error: { message } } or FastAPI { detail }.
    if (body?.error?.message) {
      message = body.error.message;
      details = body.error.details;
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (body?.detail) {
      message = JSON.stringify(body.detail);
      details = body.detail;
    }
  } catch {
    // ignore non-JSON bodies
  }
  return new ApiError(message, res.status, details);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// ---- Flows -----------------------------------------------------------------

export const flowsApi = {
  list: (projectId?: string) =>
    request<Flow[]>(`/flows${queryString({ project_id: projectId })}`),
  get: (id: string) => request<Flow>(`/flows/${id}`),
  create: (body: FlowCreate) =>
    request<Flow>("/flows", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  import: (document: FlowImport) =>
    request<Flow>("/flows/import", {
      method: "POST",
      body: JSON.stringify(document),
    }),
  update: (id: string, body: FlowUpdate) =>
    request<Flow>(`/flows/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  remove: (id: string) =>
    request<void>(`/flows/${id}`, { method: "DELETE" }),
  preview: (id: string, body: FlowPreviewRequest) =>
    request<PreviewResponse>(`/flows/${id}/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportPython: (id: string, freeIntermediates = false) =>
    request<ExportCodeResponse>(
      `/flows/${id}/export/python${
        freeIntermediates ? "?free_intermediates=true" : ""
      }`,
      {
        method: "POST",
        body: JSON.stringify({}),
      },
    ),
  createRun: (
    id: string,
    options: {
      inputDatasetId?: string;
      engine?: string;
      parameters?: Record<string, unknown> | null;
    } = {},
  ) =>
    request<FlowRun>(`/flows/${id}/runs`, {
      method: "POST",
      body: JSON.stringify({
        input_dataset_id: options.inputDatasetId,
        engine: options.engine ?? "pandas",
        // Only send when there are overrides, so flows without parameters keep
        // posting a minimal body.
        parameters:
          options.parameters && Object.keys(options.parameters).length > 0
            ? options.parameters
            : undefined,
      }),
    }),
};

// ---- Projects --------------------------------------------------------------

export const projectsApi = {
  list: () => request<Project[]>("/projects"),
  get: (id: string) => request<Project>(`/projects/${id}`),
  create: (body: ProjectCreate) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
};

// ---- Runs ------------------------------------------------------------------

export const runsApi = {
  get: (id: string) => request<FlowRun>(`/runs/${id}`),
  list: (filters: RunListFilters = {}) =>
    request<FlowRunSummary[]>(`/runs${queryString({ ...filters })}`),
  // Re-run the run's flow with the same config; returns a brand-new run.
  retry: (id: string) => request<FlowRun>(`/runs/${id}/retry`, { method: "POST" }),
};

// ---- Machine learning ------------------------------------------------------

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

// ---- Schedules -------------------------------------------------------------

export const schedulesApi = {
  list: (flowId?: string) =>
    request<Schedule[]>(`/schedules${queryString({ flow_id: flowId })}`),
  get: (id: string) => request<Schedule>(`/schedules/${id}`),
  create: (flowId: string, body: ScheduleCreate) =>
    request<Schedule>(`/flows/${flowId}/schedules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: string, body: ScheduleUpdate) =>
    request<Schedule>(`/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: string) => request<void>(`/schedules/${id}`, { method: "DELETE" }),
  runNow: (id: string) =>
    request<FlowRun>(`/schedules/${id}/run-now`, { method: "POST" }),
  runs: (id: string, limit = 100, offset = 0) =>
    request<FlowRunSummary[]>(
      `/schedules/${id}/runs${queryString({ limit, offset })}`,
    ),
};

// ---- Connections -----------------------------------------------------------

export const connectionsApi = {
  list: () => request<Connection[]>("/connections"),
  get: (id: string) => request<Connection>(`/connections/${id}`),
  providers: () => request<ProviderInfo[]>("/connections/providers"),
  create: (body: ConnectionCreate) =>
    request<Connection>("/connections", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: ConnectionUpdate) =>
    request<Connection>(`/connections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: string) => request<void>(`/connections/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    request<ConnectionTestResult>(`/connections/${id}/test`, { method: "POST" }),
  testConfig: (body: ConnectionCreate) =>
    request<ConnectionTestResult>("/connections/test-config", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  tables: (id: string) => request<TableInfo[]>(`/connections/${id}/tables`),
  objects: (id: string, prefix?: string) =>
    request<string[]>(`/connections/${id}/objects${prefix ? `?prefix=${encodeURIComponent(prefix)}` : ""}`),
};

// ---- Datasets --------------------------------------------------------------

export const datasetsApi = {
  list: (projectId?: string) =>
    request<Dataset[]>(`/datasets${queryString({ project_id: projectId })}`),
  get: (id: string) => request<Dataset>(`/datasets/${id}`),
  versions: (id: string, limit?: number) =>
    request<DatasetVersion[]>(`/datasets/${id}/versions${queryString({ limit })}`),
  flows: (id: string) => request<Flow[]>(`/datasets/${id}/flows`),
  schema: (id: string, version?: number) =>
    request<DatasetSchemaField[]>(
      `/datasets/${id}/schema${version ? `?version=${version}` : ""}`,
    ),
  sample: (id: string, version?: number) =>
    request<Record<string, unknown>[]>(
      `/datasets/${id}/sample${version ? `?version=${version}` : ""}`,
    ),
  profile: (id: string, version?: number) =>
    request<ColumnProfile[]>(
      `/datasets/${id}/profile${version ? `?version=${version}` : ""}`,
    ),
  downloadVersionUrl: (id: string, version: number) =>
    `${BASE_URL}/datasets/${id}/versions/${version}/download`,
  patch: (id: string, body: { is_disabled?: boolean }) =>
    request<Dataset>(`/datasets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" }),
  upload: async (file: File, projectId?: string): Promise<Dataset> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(
      `${BASE_URL}/datasets/upload${queryString({ project_id: projectId })}`,
      { method: "POST", body: form },
    );
    if (!res.ok) {
      throw await parseError(res);
    }
    return (await res.json()) as Dataset;
  },
};

// ---- Transformations -------------------------------------------------------

export const transformationsApi = {
  list: () => request<string[]>("/transformations"),
  preview: (body: TransformationPreviewRequest) =>
    request<PreviewResponse>("/transformations/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// ---- Catalog (backend-fed node metadata, incl. plugin nodes) ---------------

export const catalogApi = {
  nodes: () => request<CatalogNode[]>("/catalog/nodes"),
};

// ---- Plugins ---------------------------------------------------------------

export const pluginsApi = {
  list: () => request<PluginInfo[]>("/plugins"),
  diagnostics: () => request<PluginDiagnostics>("/plugins/diagnostics"),
  enable: (id: string) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/enable`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  disable: (id: string) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/disable`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  grant: (id: string, permissions: string[] = []) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/grant`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    }),
  revoke: (id: string, permissions: string[]) =>
    request<PluginInfo>(`/plugins/${encodeURIComponent(id)}/revoke`, {
      method: "POST",
      body: JSON.stringify({ permissions }),
    }),
};
