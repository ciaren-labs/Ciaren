import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { datasetsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";

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

export function useDatasetVersions(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.datasetVersions(id) : ["datasets", "none", "versions"],
    queryFn: () => datasetsApi.versions(id as string),
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.flows }); // cascade may disable flows
    },
  });
}

export function useDeleteDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => datasetsApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useUploadDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, projectId }: { file: File; projectId?: string }) =>
      datasetsApi.upload(file, projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.datasets });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}
