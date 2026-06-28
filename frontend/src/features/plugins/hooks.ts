import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { pluginsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";

export function usePluginDiagnostics() {
  return useQuery({
    queryKey: queryKeys.pluginDiagnostics,
    queryFn: () => pluginsApi.diagnostics(),
  });
}

/** Invalidate everything plugin-affected: the plugin list and the node catalog
 *  (a granted/disabled plugin adds/removes nodes from the palette live). */
function useInvalidatePlugins() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: queryKeys.plugins });
    qc.invalidateQueries({ queryKey: ["catalog"] });
    qc.invalidateQueries({ queryKey: queryKeys.transformations });
  };
}

export function useEnablePlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.enable(id),
    onSuccess: invalidate,
  });
}

export function useDisablePlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.disable(id),
    onSuccess: invalidate,
  });
}

export function useGrantPlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: ({ id, permissions = [] }: { id: string; permissions?: string[] }) =>
      pluginsApi.grant(id, permissions),
    onSuccess: invalidate,
  });
}

export function useRevokePlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: ({ id, permissions }: { id: string; permissions: string[] }) =>
      pluginsApi.revoke(id, permissions),
    onSuccess: invalidate,
  });
}
