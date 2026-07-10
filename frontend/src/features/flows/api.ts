import { queryString, request } from "@/lib/api/client";
import type { PreviewResponse } from "@/lib/types/shared";
import type { FlowRun } from "@/features/runs/types";
import type {
  CatalogNode,
  ExportCodeResponse,
  Flow,
  FlowCreate,
  FlowImport,
  FlowMigrateDocumentResponse,
  FlowPreviewRequest,
  FlowUpdate,
} from "./types";

export const flowsApi = {
  list: (projectId?: string) =>
    request<Flow[]>(`/flows${queryString({ project_id: projectId })}`),
  get: (id: string) => request<Flow>(`/flows/${id}`),
  duplicate: (id: string, name?: string) =>
    request<Flow>(`/flows/${id}/duplicate${queryString({ name })}`, { method: "POST" }),
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
  migrateDocument: (document: Record<string, unknown>) =>
    request<FlowMigrateDocumentResponse>("/flows/migrate-document", {
      method: "POST",
      body: JSON.stringify({ document }),
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

// ---- Catalog (backend-fed node metadata, incl. plugin nodes) ---------------

export const catalogApi = {
  nodes: () => request<CatalogNode[]>("/catalog/nodes"),
};
