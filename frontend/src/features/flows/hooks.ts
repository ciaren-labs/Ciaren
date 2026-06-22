import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { flowsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import type {
  FlowCreate,
  FlowPreviewRequest,
  FlowUpdate,
} from "@/lib/types";

export function useFlows(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.flowsByProject(projectId),
    queryFn: () => flowsApi.list(projectId),
  });
}

export function useFlow(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.flow(id) : ["flows", "none"],
    queryFn: () => flowsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: FlowCreate) => flowsApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.flows }),
  });
}

export function useUpdateFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: FlowUpdate }) =>
      flowsApi.update(id, body),
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      qc.invalidateQueries({ queryKey: queryKeys.flow(flow.id) });
    },
  });
}

export function useDeleteFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => flowsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.flows }),
  });
}

export function useFlowPreview(id: string) {
  return useMutation({
    mutationFn: (body: FlowPreviewRequest) => flowsApi.preview(id, body),
  });
}

export function useExportPython(id: string) {
  return useMutation({
    mutationFn: () => flowsApi.exportPython(id),
  });
}

export function useCreateRun(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (options?: { inputDatasetId?: string; engine?: string }) =>
      flowsApi.createRun(id, options ?? {}),
    // Invalidate every run query (lists + details) so history refreshes.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}
