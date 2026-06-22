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

export function useFlows() {
  return useQuery({ queryKey: queryKeys.flows, queryFn: flowsApi.list });
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
  return useMutation({
    mutationFn: (inputDatasetId?: string) =>
      flowsApi.createRun(id, inputDatasetId),
  });
}
