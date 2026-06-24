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

export function useToggleFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_disabled }: { id: string; is_disabled: boolean }) =>
      flowsApi.update(id, { is_disabled }),
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      qc.invalidateQueries({ queryKey: queryKeys.flow(flow.id) });
    },
  });
}

export function useFlowPreview(id: string) {
  return useMutation({
    mutationFn: (body: FlowPreviewRequest) => flowsApi.preview(id, body),
  });
}

export function useExportPython(id: string) {
  return useMutation({
    mutationFn: (freeIntermediates: boolean = false) =>
      flowsApi.exportPython(id, freeIntermediates),
  });
}

export function useRunFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      flowId,
      engine = "pandas",
      inputDatasetId,
    }: {
      flowId: string;
      engine?: string;
      inputDatasetId?: string;
    }) => flowsApi.createRun(flowId, { engine, inputDatasetId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: queryKeys.flows }); // refresh last_run_at
    },
  });
}

export function useCreateRun(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (options?: { inputDatasetId?: string; engine?: string }) =>
      flowsApi.createRun(id, options ?? {}),
    // Invalidate every run query (lists + details) so history refreshes, and the
    // flows list so the flow's "last run" updates.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: queryKeys.flows });
    },
  });
}
