import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { runsApi } from "@/features/runs/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type { RunListFilters } from "@/features/runs/types";

/** Filterable run history for the runs page. */
export function useRuns(filters: RunListFilters) {
  return useQuery({
    queryKey: queryKeys.runs(filters),
    queryFn: () => runsApi.list(filters),
  });
}

/**
 * Poll a run until it reaches a terminal status.
 */
export function useRun(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.run(id) : ["runs", "none"],
    queryFn: () => runsApi.get(id as string),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "success" || status === "failed" || status === "cancelled") return false;
      return 1500;
    },
  });
}

/** Re-run a run's flow with the same config (new run id). */
export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => runsApi.cancel(id),
    meta: { errorMessage: "Couldn't cancel the run" },
    onSuccess: () => {
      // The run's own task finalizes the row; the detail page's polling picks
      // the cancelled status up.
      qc.invalidateQueries({ queryKey: ["runs"] });
      toast.success("Cancellation requested");
    },
  });
}

export function useRetryRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => runsApi.retry(id),
    meta: { errorMessage: "Couldn't retry the run" },
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["flows"] }); // refresh last_run_at
      toast.success("Retry started", {
        action: { label: "View run", to: `/runs/${run.id}` },
      });
    },
  });
}
