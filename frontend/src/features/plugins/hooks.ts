import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { marketplaceApi, pluginsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";

export function usePluginDiagnostics() {
  return useQuery({
    queryKey: queryKeys.pluginDiagnostics,
    queryFn: () => pluginsApi.diagnostics(),
  });
}

export function useMarketplace() {
  return useQuery({
    queryKey: queryKeys.marketplace,
    queryFn: () => marketplaceApi.list(),
  });
}

/** License status for one plugin (premium plugins register a provider; community
 *  plugins report "no license provider"). Used to show a license badge. */
export function usePluginLicense(id: string) {
  return useQuery({
    queryKey: queryKeys.pluginLicense(id),
    queryFn: () => pluginsApi.license(id),
  });
}

/** Invalidate everything plugin-affected: the plugin list, the "Explore" catalog
 *  (installed flags change), and the node catalog (a granted/disabled plugin
 *  adds/removes nodes from the palette live). */
function useInvalidatePlugins() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: queryKeys.plugins });
    qc.invalidateQueries({ queryKey: queryKeys.marketplace });
    qc.invalidateQueries({ queryKey: ["catalog"] });
    qc.invalidateQueries({ queryKey: queryKeys.transformations });
  };
}

export function useInstallPlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (file: File) => pluginsApi.install(file),
    // The install button renders result messages (success and failure) inline.
    meta: { suppressErrorToast: true },
    onSuccess: invalidate,
  });
}

export function useInstallFromMarketplace() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => marketplaceApi.install(id),
    // The marketplace card renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: invalidate,
  });
}

export function useEnablePlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.enable(id),
    meta: { errorMessage: "Couldn't enable the plugin" },
    onSuccess: (plugin) => {
      invalidate();
      toast.success(`Plugin "${plugin.name}" enabled`);
    },
  });
}

export function useDisablePlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.disable(id),
    meta: { errorMessage: "Couldn't disable the plugin" },
    onSuccess: (plugin) => {
      invalidate();
      toast.success(`Plugin "${plugin.name}" disabled`);
    },
  });
}

export function useUninstallPlugin() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.uninstall(id),
    meta: { errorMessage: "Couldn't uninstall the plugin" },
    onSuccess: (result) => {
      invalidate();
      toast.success(
        result.removed ? "Plugin uninstalled" : "Plugin removed (no managed files to delete)",
      );
    },
  });
}

/** Activate a pasted license token. Invalidating the whole "plugins" key also
 *  refreshes the per-plugin license badge (its key nests under "plugins"). */
export function useActivateLicense() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: ({ id, token }: { id: string; token: unknown }) =>
      pluginsApi.activateLicense(id, token),
    // The license dialog renders failures inline (a rejected token needs context).
    meta: { suppressErrorToast: true },
    onSuccess: (status) => {
      invalidate();
      if (status.valid) toast.success("License activated");
    },
  });
}

export function useRemoveLicense() {
  const invalidate = useInvalidatePlugins();
  return useMutation({
    mutationFn: (id: string) => pluginsApi.removeLicense(id),
    meta: { errorMessage: "Couldn't remove the license" },
    onSuccess: () => {
      invalidate();
      toast.success("License removed from this machine");
    },
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
