import { authHeaders, BASE_URL, parseError, queryString, request } from "@/lib/api/client";
import type { ColumnProfile } from "@/lib/types/shared";
import type { Flow } from "@/features/flows/types";
import type { Dataset, DatasetSchemaField, DatasetVersion, UploadParseOptions } from "./types";

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
  upload: async (
    file: File,
    projectId?: string,
    options?: UploadParseOptions,
  ): Promise<Dataset> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(
      `${BASE_URL}/datasets/upload${queryString({ project_id: projectId, ...options })}`,
      { method: "POST", body: form, headers: authHeaders() },
    );
    if (!res.ok) {
      throw await parseError(res);
    }
    return (await res.json()) as Dataset;
  },
};
