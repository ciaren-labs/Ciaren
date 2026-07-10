import { MutationCache, QueryClient } from "@tanstack/react-query";
import { toast } from "@/stores/toastStore";
import { friendlyErrorMessage } from "@/lib/errors";
import type { RunListFilters } from "@/features/runs/types";

// Mutation meta contract, enforced app-wide:
//  - errorMessage: title for the automatic failure toast (default "Action failed").
//  - suppressErrorToast: opt out for mutations whose errors are rendered inline
//    (dialog forms, upload dropzones) so the user isn't told twice.
declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: {
      errorMessage?: string;
      suppressErrorToast?: boolean;
    };
  }
}

export const queryClient = new QueryClient({
  // Every mutation failure surfaces as a toast unless the call site opted out —
  // no action should ever fail silently.
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (mutation.meta?.suppressErrorToast) return;
      toast.error(mutation.meta?.errorMessage ?? "Action failed", {
        description: friendlyErrorMessage(error),
      });
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      // Local-first app: the backend is typically on localhost, reachable even
      // when the browser thinks it's offline. The default "online" mode pauses
      // queries indefinitely on an offline signal, which strands pages in a
      // pending state that looks like an empty workspace.
      networkMode: "always",
    },
    mutations: {
      networkMode: "always",
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
  connectionObjects: (id: string, prefix?: string) =>
    ["connections", id, "objects", { prefix: prefix ?? "" }] as const,
  plugins: ["plugins"] as const,
  pluginDiagnostics: ["plugins", "diagnostics"] as const,
  pluginLicense: (id: string) => ["plugins", id, "license"] as const,
  marketplace: ["marketplace"] as const,
  appSettings: ["app-settings"] as const,
};
