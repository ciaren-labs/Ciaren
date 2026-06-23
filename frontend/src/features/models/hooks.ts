import { useQuery } from "@tanstack/react-query";
import { mlApi, transformationsApi } from "@/lib/api";

/** ML is "on" when the backend lists at least one ML node type — the same signal
 * the node palette uses (ML_ENABLED + the [ml] extra installed). */
export function useMlEnabled() {
  const { data } = useQuery({
    queryKey: ["transformations", "available"],
    queryFn: () => transformationsApi.list(),
    staleTime: 5 * 60 * 1000,
  });
  return (data ?? []).includes("mlTrain");
}

export function useRegisteredModels() {
  return useQuery({
    queryKey: ["ml", "models"],
    queryFn: () => mlApi.registeredModels(),
  });
}

export function useMlExperiments() {
  return useQuery({
    queryKey: ["ml", "experiments"],
    queryFn: () => mlApi.allExperiments(),
  });
}

export function useExperimentRuns(experimentId: string | null) {
  return useQuery({
    queryKey: ["ml", "experiments", experimentId, "runs"],
    queryFn: () => mlApi.experimentRuns(experimentId!),
    enabled: experimentId !== null,
  });
}
