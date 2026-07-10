import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/features/settings/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type { AppSetting } from "@/features/settings/types";

export function useAppSettings() {
  return useQuery({
    queryKey: queryKeys.appSettings,
    queryFn: settingsApi.list,
  });
}

/** Replace one setting in the cached list (PUT/DELETE return the fresh item). */
function patchCache(qc: ReturnType<typeof useQueryClient>, updated: AppSetting) {
  qc.setQueryData<AppSetting[]>(queryKeys.appSettings, (prev) =>
    prev?.map((s) => (s.key === updated.key ? updated : s)),
  );
}

export function useUpdateAppSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: number | string }) =>
      settingsApi.update(key, value),
    meta: { errorMessage: "Couldn't save the setting" },
    onSuccess: (updated) => {
      patchCache(qc, updated);
      toast.success(`${updated.label} saved`, {
        description: updated.restart_required
          ? "Takes full effect after the server restarts."
          : "Applied immediately.",
      });
    },
  });
}

export function useResetAppSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => settingsApi.reset(key),
    meta: { errorMessage: "Couldn't reset the setting" },
    onSuccess: (updated) => {
      patchCache(qc, updated);
      toast.success(`${updated.label} reset`, {
        description:
          updated.source === "env"
            ? "Now following the server's environment variable."
            : "Back to the built-in default.",
      });
    },
  });
}
