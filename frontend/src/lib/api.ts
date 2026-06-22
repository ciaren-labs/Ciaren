// Centralized, typed API client for the FlowFrame backend.
// All requests go through the Vite dev proxy: /api -> http://localhost:8000

import type {
  Dataset,
  DatasetSchemaField,
  DatasetVersion,
  ExportCodeResponse,
  Flow,
  FlowCreate,
  FlowPreviewRequest,
  FlowRun,
  FlowUpdate,
  PreviewResponse,
  TransformationPreviewRequest,
} from "./types";

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
  list: () => request<Flow[]>("/flows"),
  get: (id: string) => request<Flow>(`/flows/${id}`),
  create: (body: FlowCreate) =>
    request<Flow>("/flows", {
      method: "POST",
      body: JSON.stringify(body),
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
  exportPython: (id: string) =>
    request<ExportCodeResponse>(`/flows/${id}/export/python`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  createRun: (id: string, inputDatasetId?: string) =>
    request<FlowRun>(`/flows/${id}/runs`, {
      method: "POST",
      body: JSON.stringify({ input_dataset_id: inputDatasetId }),
    }),
};

// ---- Runs ------------------------------------------------------------------

export const runsApi = {
  get: (id: string) => request<FlowRun>(`/runs/${id}`),
};

// ---- Datasets --------------------------------------------------------------

export const datasetsApi = {
  list: () => request<Dataset[]>("/datasets"),
  get: (id: string) => request<Dataset>(`/datasets/${id}`),
  versions: (id: string) =>
    request<DatasetVersion[]>(`/datasets/${id}/versions`),
  schema: (id: string, version?: number) =>
    request<DatasetSchemaField[]>(
      `/datasets/${id}/schema${version ? `?version=${version}` : ""}`,
    ),
  sample: (id: string, version?: number) =>
    request<Record<string, unknown>[]>(
      `/datasets/${id}/sample${version ? `?version=${version}` : ""}`,
    ),
  upload: async (file: File): Promise<Dataset> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE_URL}/datasets/upload`, {
      method: "POST",
      body: form,
    });
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
