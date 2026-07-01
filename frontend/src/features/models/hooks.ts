import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { mlApi, transformationsApi } from "@/lib/api";

/** ML is "on" when the backend lists at least one ML node type — the same signal
 * the node palette uses (CIAREN_ML_ENABLED, on by default). */
export function useMlEnabled() {
  const { data } = useQuery({
    queryKey: ["transformations", "available"],
    queryFn: () => transformationsApi.list(),
    staleTime: 5 * 60 * 1000,
  });
  return (data ?? []).includes("mlTrainClassifier");
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

export function useSetModelAlias() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ model, alias, version }: { model: string; alias: string; version: string }) =>
      mlApi.setAlias(model, alias, version),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ml", "models"] }),
  });
}

export function useClearModelAlias() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ model, alias }: { model: string; alias: string }) =>
      mlApi.clearAlias(model, alias),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ml", "models"] }),
  });
}
