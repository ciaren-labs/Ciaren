import { queryString, request } from "@/lib/api/client";
import type { FlowRun, FlowRunSummary, RunListFilters } from "./types";

export const runsApi = {
  get: (id: string) => request<FlowRun>(`/runs/${id}`),
  list: (filters: RunListFilters = {}) =>
    request<FlowRunSummary[]>(`/runs${queryString({ ...filters })}`),
  // Re-run the run's flow with the same config; returns a brand-new run.
  retry: (id: string) => request<FlowRun>(`/runs/${id}/retry`, { method: "POST" }),
  cancel: (id: string) =>
    request<{ run_id: string; status: string }>(`/runs/${id}/cancel`, { method: "POST" }),
};
