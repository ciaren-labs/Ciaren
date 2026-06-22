import { useQuery } from "@tanstack/react-query";
import { runsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import type { RunListFilters } from "@/lib/types";

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
      if (status === "success" || status === "failed") return false;
      return 1500;
    },
  });
}
