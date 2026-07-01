import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { schedulesApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type { ScheduleCreate, ScheduleUpdate } from "@/lib/types";

export function useSchedules(flowId?: string) {
  return useQuery({
    queryKey: queryKeys.schedulesByFlow(flowId),
    queryFn: () => schedulesApi.list(flowId),
  });
}

export function useSchedule(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.schedule(id) : ["schedules", "none"],
    queryFn: () => schedulesApi.get(id as string),
    enabled: !!id,
  });
}

/** Run history for one schedule (links into the shared /runs/:id detail page). */
export function useScheduleRuns(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.scheduleRuns(id) : ["schedules", "none", "runs"],
    queryFn: () => schedulesApi.runs(id as string),
    enabled: !!id,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ flowId, body }: { flowId: string; body: ScheduleCreate }) =>
      schedulesApi.create(flowId, body),
    // The schedule form dialog renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: (schedule) => {
      qc.invalidateQueries({ queryKey: queryKeys.schedules });
      toast.success(schedule.name ? `Schedule "${schedule.name}" created` : "Schedule created");
    },
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ScheduleUpdate }) =>
      schedulesApi.update(id, body),
    meta: { errorMessage: "Couldn't update the schedule" },
    onSuccess: (schedule) => {
      qc.invalidateQueries({ queryKey: queryKeys.schedules });
      qc.invalidateQueries({ queryKey: queryKeys.schedule(schedule.id) });
      toast.success(schedule.name ? `Schedule "${schedule.name}" updated` : "Schedule updated");
    },
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schedulesApi.remove(id),
    meta: { errorMessage: "Couldn't delete the schedule" },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.schedules });
      toast.success("Schedule deleted");
    },
  });
}

/** Fire a schedule immediately (stays out of the retry/auto-disable machinery). */
export function useRunScheduleNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schedulesApi.runNow(id),
    meta: { errorMessage: "Couldn't start the run" },
    onSuccess: (run, id) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["flows"] }); // refresh last_run_at
      qc.invalidateQueries({ queryKey: queryKeys.schedules });
      qc.invalidateQueries({ queryKey: queryKeys.scheduleRuns(id) });
      toast.success("Run started", {
        action: { label: "View run", to: `/runs/${run.id}` },
      });
    },
  });
}
