import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { datasetsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";

export function useDatasets(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.datasetsByProject(projectId),
    queryFn: () => datasetsApi.list(projectId),
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
      toast.success("Dataset deleted");
    },
  });
}

export function useUploadDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, projectId }: { file: File; projectId?: string }) =>
      datasetsApi.upload(file, projectId),
    // The upload dropzone shows failures inline, next to where the file was dropped.
    meta: { suppressErrorToast: true },
    onSuccess: (dataset) => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
      toast.success(`Dataset "${dataset.name}" uploaded`);
    },
  });
}
