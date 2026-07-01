import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  CalendarClock,
  Clock,
  Cpu,
  Loader2,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Trash2,
  Workflow,
} from "lucide-react";
import {
  useDeleteSchedule,
  useRunScheduleNow,
  useSchedule,
  useScheduleRuns,
  useUpdateSchedule,
} from "./hooks";
import { ScheduleFormDialog } from "./ScheduleFormDialog";
import { ScheduleStateBadge } from "./SchedulesPage";
import { useFlow } from "@/features/flows/hooks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { formatDuration } from "@/lib/format";
import { describeCron } from "@/lib/cron";

export function ScheduleDetailPage() {
  const { scheduleId } = useParams<{ scheduleId: string }>();
  const navigate = useNavigate();
  const fmt = useFormatDateTime();

  const { data: schedule, isLoading } = useSchedule(scheduleId ?? null);
  const { data: flow } = useFlow(schedule?.flow_id ?? null);
  const { data: runs } = useScheduleRuns(scheduleId ?? null);

  const updateSchedule = useUpdateSchedule();
  const deleteSchedule = useDeleteSchedule();
  const runNow = useRunScheduleNow();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading schedule…
      </div>
    );
  }
  if (!schedule) {
    return <div className="p-6 text-sm text-destructive">Schedule not found.</div>;
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      {/* Header */}
      <div className="mb-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            onClick={() => navigate("/schedules")}
            className="mb-2 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Schedules
          </button>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
              <CalendarClock className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-xl font-semibold">
                  {schedule.name || "Untitled schedule"}
                </h1>
                <ScheduleStateBadge schedule={schedule} />
              </div>
              <button
                onClick={() => navigate(`/flows/${schedule.flow_id}`)}
                className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <Workflow className="h-3.5 w-3.5" /> {flow?.name ?? "Open flow"}
              </button>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => runNow.mutate(schedule.id, { onSuccess: (run) => navigate(`/runs/${run.id}`) })}
            disabled={runNow.isPending}
          >
            {runNow.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run now
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => updateSchedule.mutate({ id: schedule.id, body: { is_enabled: !schedule.is_enabled } })}
            disabled={updateSchedule.isPending}
          >
            {schedule.is_enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {schedule.is_enabled ? "Pause" : "Resume"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" /> Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmDelete(true)}
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" /> Delete
          </Button>
        </div>
      </div>

      {schedule.description && (
        <p className="mb-4 text-sm text-muted-foreground">{schedule.description}</p>
      )}

      {schedule.disabled_reason && (
        <div className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Auto-disabled: {schedule.disabled_reason}. Resume to clear the failure streak and
            recompute the next run.
          </span>
        </div>
      )}

      {/* Config summary */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <InfoCard icon={Clock} label="Interval">
          <div>{describeCron(schedule.cron)}</div>
          <code className="text-[11px] text-muted-foreground">{schedule.cron}</code>
        </InfoCard>
        <InfoCard icon={CalendarClock} label="Timezone">
          {schedule.timezone}
        </InfoCard>
        <InfoCard icon={Cpu} label="Engine">
          {schedule.engine ?? "Server default"}
        </InfoCard>
        <InfoCard icon={CalendarClock} label="Next run">
          {schedule.is_enabled ? fmt(schedule.next_run_at) : "Paused"}
        </InfoCard>
        <InfoCard icon={Clock} label="Last fired">
          {schedule.last_fired_at ? (
            <button
              className="flex items-center gap-1.5 hover:underline disabled:cursor-default disabled:no-underline"
              disabled={!schedule.last_run_id}
              onClick={() => schedule.last_run_id && navigate(`/runs/${schedule.last_run_id}`)}
            >
              {fmt(schedule.last_fired_at)}
              {schedule.last_status && <StatusBadge status={schedule.last_status} />}
            </button>
          ) : (
            "Never"
          )}
        </InfoCard>
        <InfoCard icon={RefreshCw} label="Reliability">
          <div className="text-xs text-muted-foreground">
            {schedule.consecutive_failures} consecutive failure
            {schedule.consecutive_failures !== 1 ? "s" : ""}
            {schedule.max_retries > 0 && ` · up to ${schedule.max_retries} retries`}
            {schedule.catch_up && " · catch-up on"}
          </div>
        </InfoCard>
      </div>

      {/* Run history */}
      <h2 className="mb-2 text-sm font-semibold">Run history</h2>
      {!runs || runs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          This schedule hasn't produced any runs yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-semibold">Status</th>
                <th className="px-4 py-2.5 text-left font-semibold">Trigger</th>
                <th className="px-4 py-2.5 text-left font-semibold">Engine</th>
                <th className="px-4 py-2.5 text-left font-semibold">Started</th>
                <th className="px-4 py-2.5 text-left font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  onClick={() => navigate(`/runs/${run.id}`)}
                  className="cursor-pointer border-t border-border transition-colors hover:bg-accent/40"
                >
                  <td className="px-4 py-2.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground capitalize">{run.trigger}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{run.engine}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{fmt(run.created_at)}</td>
                  <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ScheduleFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        schedule={schedule}
        submitting={updateSchedule.isPending}
        error={updateSchedule.error}
        onSubmit={(_flowId, body) =>
          updateSchedule.mutate({ id: schedule.id, body }, { onSuccess: () => setEditOpen(false) })
        }
      />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete "${schedule.name || "this schedule"}"?`}
        description={<p>The schedule will stop firing. Past runs stay in your run history.</p>}
        confirmLabel="Delete"
        variant="destructive"
        isPending={deleteSchedule.isPending}
        onConfirm={() =>
          deleteSchedule.mutate(schedule.id, { onSuccess: () => navigate("/schedules") })
        }
      />
    </div>
  );
}

function InfoCard({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof Clock;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className="text-sm">{children}</div>
    </div>
  );
}
