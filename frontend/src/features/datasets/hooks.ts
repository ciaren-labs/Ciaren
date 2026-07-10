import type { UploadParseOptions } from "@/features/datasets/types";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { datasetsApi } from "@/features/datasets/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";

export function useDatasets(projectId?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.datasetsByProject(projectId),
    queryFn: () => datasetsApi.list(projectId),
    enabled,
  });
}

export function useDatasetSchema(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.datasetSchema(id) : ["datasets", "none", "schema"],
    queryFn: () => datasetsApi.schema(id as string),
    enabled: !!id,
  });
}

export function useDatasetVersions(id: string | null, limit?: number) {
  return useQuery({
    queryKey: id ? queryKeys.datasetVersions(id, limit) : ["datasets", "none", "versions"],
    queryFn: () => datasetsApi.versions(id as string, limit),
    enabled: !!id,
  });
}

export function useDatasetSample(id: string | null, version?: number) {
  return useQuery({
    queryKey: id
      ? queryKeys.datasetSample(id, version)
      : ["datasets", "none", "sample"],
    queryFn: () => datasetsApi.sample(id as string, version),
    enabled: !!id,
  });
}

export function useDatasetProfile(id: string | null, version?: number) {
  return useQuery({
    queryKey: id ? queryKeys.datasetProfile(id, version) : ["datasets", "none", "profile"],
    queryFn: () => datasetsApi.profile(id as string, version),
    enabled: !!id,
  });
}

export function useDatasetFlows(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.datasetFlows(id) : ["datasets", "none", "flows"],
    queryFn: () => datasetsApi.flows(id as string),
    enabled: !!id,
  });
}

export function usePatchDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { is_disabled?: boolean } }) =>
      datasetsApi.patch(id, body),
    meta: { errorMessage: "Couldn't update the dataset" },
    onSuccess: (dataset) => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.flows }); // cascade may disable flows
      toast.success(
        dataset.is_disabled
          ? `Dataset "${dataset.name}" disabled`
          : `Dataset "${dataset.name}" enabled`,
      );
    },
  });
}

export function useDeleteDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => datasetsApi.remove(id),
    meta: { errorMessage: "Couldn't delete the dataset" },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      // Deleting a dataset cascades to disable the flows that read from it
      // (backend DELETE /datasets/{id} → disable_flows_for_dataset), same as
      // the PATCH-disable path — so refresh flows or the list keeps showing
      // them enabled until the next refetch.
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success("Dataset deleted");
    },
  });
}

export function useUploadDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      projectId,
      options,
    }: {
      file: File;
      projectId?: string;
      options?: UploadParseOptions;
    }) => datasetsApi.upload(file, projectId, options),
    // The upload dropzone shows failures inline, next to where the file was dropped.
    meta: { suppressErrorToast: true },
    onSuccess: (dataset) => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      const dialect = dataset.parse_options;
      const detected = dialect
        ? ` (dialect: ${[
            dialect.delimiter === "	" ? "tab" : dialect.delimiter,
            dialect.encoding,
            dialect.decimal === "," ? "decimal ," : null,
            dialect.sheet !== undefined ? `sheet ${dialect.sheet}` : null,
          ]
            .filter(Boolean)
            .join(" · ")})`
        : "";
      toast.success(`Dataset "${dataset.name}" uploaded${detected}`);
    },
  });
}
