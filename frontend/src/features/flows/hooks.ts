import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { flowsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type {
  FlowCreate,
  FlowImport,
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
    meta: { errorMessage: "Couldn't create the flow" },
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success(`Flow "${flow.name}" created`);
    },
  });
}

export function useImportFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (document: FlowImport) => flowsApi.import(document),
    // The import dialog shows failures inline, next to the name field.
    meta: { suppressErrorToast: true },
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success(`Flow "${flow.name}" imported`);
    },
  });
}

export function useMigrateFlowDocument() {
  return useMutation({
    mutationFn: (document: Record<string, unknown>) =>
      flowsApi.migrateDocument(document),
    // Both call sites (the import-dialog outdated-file warning and the
    // standalone migrate utility) render/swallow errors inline.
    meta: { suppressErrorToast: true },
  });
}

export function useUpdateFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: FlowUpdate }) =>
      flowsApi.update(id, body),
    meta: { errorMessage: "Couldn't save the flow" },
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      qc.invalidateQueries({ queryKey: queryKeys.flow(flow.id) });
    },
  });
}

export function useDuplicateFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => flowsApi.duplicate(id),
    meta: { errorMessage: "Couldn't duplicate the flow" },
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: ["flows"] });
      toast.success(`Duplicated as "${flow.name}"`);
    },
  });
}

export function useDeleteFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => flowsApi.remove(id),
    meta: { errorMessage: "Couldn't delete the flow" },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      toast.success("Flow deleted");
    },
  });
}

export function useToggleFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_disabled }: { id: string; is_disabled: boolean }) =>
      flowsApi.update(id, { is_disabled }),
    meta: { errorMessage: "Couldn't update the flow" },
    onSuccess: (flow) => {
      qc.invalidateQueries({ queryKey: queryKeys.flows });
      qc.invalidateQueries({ queryKey: queryKeys.flow(flow.id) });
      toast.success(flow.is_disabled ? `Flow "${flow.name}" disabled` : `Flow "${flow.name}" enabled`);
    },
  });
}

export function useFlowPreview(id: string) {
  return useMutation({
    mutationFn: (body: FlowPreviewRequest) => flowsApi.preview(id, body),
    // The preview panel renders failures inline, next to the results area.
    meta: { suppressErrorToast: true },
  });
}

export function useExportPython(id: string) {
  return useMutation({
    mutationFn: (freeIntermediates: boolean = false) =>
      flowsApi.exportPython(id, freeIntermediates),
    // The export dialog renders failures inline.
    meta: { suppressErrorToast: true },
  });
}

export function useRunFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      flowId,
      engine = "pandas",
      inputDatasetId,
      parameters,
    }: {
      flowId: string;
      engine?: string;
      inputDatasetId?: string;
      parameters?: Record<string, unknown> | null;
    }) => flowsApi.createRun(flowId, { engine, inputDatasetId, parameters }),
    // The quick-run dialog shows failures inline, next to the Run button.
    meta: { suppressErrorToast: true },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: queryKeys.flows }); // refresh last_run_at
    },
  });
}

export function useCreateRun(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (options?: {
      inputDatasetId?: string;
      engine?: string;
      parameters?: Record<string, unknown> | null;
    }) => flowsApi.createRun(id, options ?? {}),
    meta: { errorMessage: "Couldn't start the run" },
    // Invalidate every run query (lists + details) so history refreshes, and the
    // flows list so the flow's "last run" updates.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: queryKeys.flows });
    },
  });
}
