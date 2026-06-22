import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { datasetsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";

export function useDatasets() {
  return useQuery({ queryKey: queryKeys.datasets, queryFn: datasetsApi.list });
}

export function useDatasetSchema(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.datasetSchema(id) : ["datasets", "none", "schema"],
    queryFn: () => datasetsApi.schema(id as string),
    enabled: !!id,
  });
}

export function useUploadDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => datasetsApi.upload(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.datasets }),
  });
}
