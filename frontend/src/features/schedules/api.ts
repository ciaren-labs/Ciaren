import { queryString, request } from "@/lib/api/client";
import type { FlowRun, FlowRunSummary } from "@/features/runs/types";
import type { Schedule, ScheduleCreate, ScheduleUpdate } from "./types";

export const schedulesApi = {
  list: (flowId?: string) =>
    request<Schedule[]>(`/schedules${queryString({ flow_id: flowId })}`),
  get: (id: string) => request<Schedule>(`/schedules/${id}`),
  create: (flowId: string, body: ScheduleCreate) =>
    request<Schedule>(`/flows/${flowId}/schedules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: string, body: ScheduleUpdate) =>
    request<Schedule>(`/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: string) => request<void>(`/schedules/${id}`, { method: "DELETE" }),
  runNow: (id: string) =>
    request<FlowRun>(`/schedules/${id}/run-now`, { method: "POST" }),
  runs: (id: string, limit = 100, offset = 0) =>
    request<FlowRunSummary[]>(
      `/schedules/${id}/runs${queryString({ limit, offset })}`,
    ),
};
