import { QueryClient } from "@tanstack/react-query";
import type { RunListFilters } from "./types";

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
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  flows: ["flows"] as const,
  flowsByProject: (projectId?: string) => ["flows", { projectId }] as const,
  flow: (id: string) => ["flows", id] as const,
  datasets: ["datasets"] as const,
  datasetsByProject: (projectId?: string) => ["datasets", { projectId }] as const,
  dataset: (id: string) => ["datasets", id] as const,
  datasetSchema: (id: string) => ["datasets", id, "schema"] as const,
  datasetSample: (id: string, version?: number) =>
    ["datasets", id, "sample", version ?? "latest"] as const,
  datasetVersions: (id: string, limit?: number) => ["datasets", id, "versions", { limit }] as const,
  datasetFlows: (id: string) => ["datasets", id, "flows"] as const,
  datasetProfile: (id: string, version?: number) =>
    ["datasets", id, "profile", version ?? "latest"] as const,
  run: (id: string) => ["runs", id] as const,
  runs: (filters: RunListFilters) => ["runs", "list", filters] as const,
  schedules: ["schedules"] as const,
  schedulesByFlow: (flowId?: string) => ["schedules", { flowId }] as const,
  schedule: (id: string) => ["schedules", id] as const,
  scheduleRuns: (id: string) => ["schedules", id, "runs"] as const,
  transformations: ["transformations"] as const,
  connections: ["connections"] as const,
  connectionProviders: ["connections", "providers"] as const,
  connectionTables: (id: string) => ["connections", id, "tables"] as const,
  connectionObjects: (id: string) => ["connections", id, "objects"] as const,
  plugins: ["plugins"] as const,
  pluginDiagnostics: ["plugins", "diagnostics"] as const,
  marketplace: ["marketplace"] as const,
};
