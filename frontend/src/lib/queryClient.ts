import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

export const queryKeys = {
  flows: ["flows"] as const,
  flow: (id: string) => ["flows", id] as const,
  datasets: ["datasets"] as const,
  dataset: (id: string) => ["datasets", id] as const,
  datasetSchema: (id: string) => ["datasets", id, "schema"] as const,
  datasetSample: (id: string) => ["datasets", id, "sample"] as const,
  run: (id: string) => ["runs", id] as const,
  transformations: ["transformations"] as const,
};
