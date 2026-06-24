import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  CalendarClock,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useRunScheduleNow,
  useSchedules,
  useUpdateSchedule,
} from "./hooks";
import { ScheduleFormDialog } from "./ScheduleFormDialog";
import { useFlows } from "@/features/flows/hooks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { FilterBar, FilterField } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { ViewToggle } from "@/components/filters/ViewToggle";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import { describeCron } from "@/lib/cron";
import type { Schedule } from "@/lib/types";
import { cn } from "@/lib/utils";

const ENABLED_OPTIONS = [
  { value: "enabled", label: "Active" },
  { value: "paused", label: "Paused" },
];

/** Lifecycle pill: paused vs auto-disabled vs active. */
export function ScheduleStateBadge({ schedule }: { schedule: Schedule }) {
  if (schedule.disabled_reason) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] font-medium text-destructive"
        title={schedule.disabled_reason}
      >
        <AlertCircle className="h-3 w-3" /> Auto-disabled
      </span>
    );
  }
  if (!schedule.enabled) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
        <Pause className="h-3 w-3" /> Paused
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
      <CalendarClock className="h-3 w-3" /> Active
    </span>
  );
}

export function SchedulesPage() {
  const navigate = useNavigate();
  const fmt = useFormatDateTime();
  const { data: schedules, isLoading } = useSchedules();
  const { data: flows } = useFlows();
  const createSchedule = useCreateSchedule();
  const updateSchedule = useUpdateSchedule();
  const deleteSchedule = useDeleteSchedule();
  const runNow = useRunScheduleNow();

  const [layout, setLayout] = useLayoutPreference("schedules", "table");
  const [flowId, setFlowId] = useState("");
  const [state, setState] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Schedule | null>(null);

  const flowName = useMemo(
    () => new Map((flows ?? []).map((f) => [f.id, f.name])),
    [flows],
  );

  const filtered = useMemo(() => {
    let list = schedules ?? [];
    if (flowId) list = list.filter((s) => s.flow_id === flowId);
    if (state === "enabled") list = list.filter((s) => s.enabled);
    if (state === "paused") list = list.filter((s) => !s.enabled);
    return list;
  }, [schedules, flowId, state]);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (s: Schedule) => {
    setEditing(s);
    setFormOpen(true);
  };

  const handleSubmit = (flow: string, body: Parameters<typeof createSchedule.mutate>[0]["body"]) => {
    if (editing) {
      updateSchedule.mutate(
        { id: editing.id, body },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createSchedule.mutate({ flowId: flow, body }, { onSuccess: () => setFormOpen(false) });
    }
  };

  const toggle = (s: Schedule) =>
    updateSchedule.mutate({ id: s.id, body: { enabled: !s.enabled } });

  const actions = {
    open: (s: Schedule) => navigate(`/schedules/${s.id}`),
    edit: openEdit,
    toggle,
    runNow: (s: Schedule) =>
      runNow.mutate(s.id, { onSuccess: (run) => navigate(`/runs/${run.id}`) }),
    remove: (s: Schedule) => setPendingDelete(s),
  };

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <CalendarClock className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Schedules</h1>
            <p className="text-xs text-muted-foreground">
              Run flows automatically on a cron cadence. Scheduled runs appear in your run history.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ViewToggle value={layout} onChange={setLayout} />
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" /> New schedule
          </Button>
        </div>
      </div>

      {/* Filters */}
      <FilterBar className="mb-4">
        <FilterField label="Flow">
          <SearchableSelect
            value={flowId}
            onChange={setFlowId}
            allLabel="All flows"
            placeholder="Search flows…"
            options={(flows ?? []).map((f) => ({ value: f.id, label: f.name }))}
          />
        </FilterField>
        <FilterField label="State" className="min-w-[8rem]">
          <SearchableSelect
            value={state}
            onChange={setState}
            allLabel="Any state"
            placeholder="Search…"
            options={ENABLED_OPTIONS}
          />
        </FilterField>
      </FilterBar>

      {(updateSchedule.isError || deleteSchedule.isError || runNow.isError) && (
        <div className="mb-4 flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {((updateSchedule.error || deleteSchedule.error || runNow.error) as Error)?.message ??
            "Operation failed."}
        </div>
      )}

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading schedules…
        </p>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-10 text-center">
          <p className="text-sm text-muted-foreground">
            {flowId || state
              ? "No schedules match these filters."
              : "No schedules yet. Create one to run a flow automatically."}
          </p>
        </div>
      ) : layout === "table" ? (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-semibold">Name</th>
                <th className="px-4 py-2.5 text-left font-semibold">Flow</th>
                <th className="px-4 py-2.5 text-left font-semibold">Interval</th>
                <th className="px-4 py-2.5 text-left font-semibold">Next run</th>
                <th className="px-4 py-2.5 text-left font-semibold">Last</th>
                <th className="px-4 py-2.5 text-left font-semibold">State</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => actions.open(s)}
                  className="cursor-pointer border-t border-border transition-colors hover:bg-accent/40"
                >
                  <td className="px-4 py-2.5 font-medium">{s.name || "Untitled schedule"}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {flowName.get(s.flow_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{describeCron(s.cron)}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {s.enabled ? fmt(s.next_run_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {s.last_status ? <StatusBadge status={s.last_status} /> : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <ScheduleStateBadge schedule={s} />
                  </td>
                  <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <RowActions schedule={s} actions={actions} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s) => (
            <ScheduleCard
              key={s.id}
              schedule={s}
              flowName={flowName.get(s.flow_id)}
              fmt={fmt}
              actions={actions}
            />
          ))}
        </div>
      )}

      <ScheduleFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        schedule={editing}
        submitting={createSchedule.isPending || updateSchedule.isPending}
        error={createSchedule.error || updateSchedule.error}
        onSubmit={handleSubmit}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title={`Delete "${pendingDelete?.name || "this schedule"}"?`}
        description={
          <p>
            The schedule will stop firing. Past runs it produced stay in your run history.
          </p>
        }
        confirmLabel="Delete"
        variant="destructive"
        isPending={deleteSchedule.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          const id = pendingDelete.id;
          setPendingDelete(null);
          deleteSchedule.mutate(id);
        }}
      />
    </div>
  );
}

interface Actions {
  open: (s: Schedule) => void;
  edit: (s: Schedule) => void;
  toggle: (s: Schedule) => void;
  runNow: (s: Schedule) => void;
  remove: (s: Schedule) => void;
}

function RowActions({ schedule, actions }: { schedule: Schedule; actions: Actions }) {
  return (
    <div className="flex items-center justify-end gap-1">
      <button
        onClick={() => actions.runNow(schedule)}
        className="rounded-md p-1.5 text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700"
        title="Run now"
      >
        <Play className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => actions.toggle(schedule)}
        className={cn(
          "rounded-md p-1.5 transition-colors hover:bg-muted",
          schedule.enabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
        )}
        title={schedule.enabled ? "Pause" : "Resume"}
      >
        {schedule.enabled ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </button>
      <button
        onClick={() => actions.edit(schedule)}
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        title="Edit"
      >
        <Pencil className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => actions.remove(schedule)}
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
        title="Delete"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function ScheduleCard({
  schedule,
  flowName,
  fmt,
  actions,
}: {
  schedule: Schedule;
  flowName?: string;
  fmt: (iso: string | null | undefined) => string;
  actions: Actions;
}) {
  return (
    <div
      className={cn(
        "group animate-fade-in-up flex flex-col rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md",
        schedule.disabled_reason
          ? "border-destructive/30"
          : !schedule.enabled
            ? "border-amber-300 opacity-80"
            : "border-border",
      )}
    >
      <button onClick={() => actions.open(schedule)} className="flex-1 text-left">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-semibold">{schedule.name || "Untitled schedule"}</span>
          <ScheduleStateBadge schedule={schedule} />
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {flowName ?? "Unknown flow"}
        </p>
        <p className="mt-2 text-sm">{describeCron(schedule.cron)}</p>
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <CalendarClock className="h-3.5 w-3.5" />
          {schedule.enabled ? `Next: ${fmt(schedule.next_run_at)}` : "Paused"}
        </div>
      </button>
      <div
        className="mt-3 flex items-center justify-end gap-1 border-t border-border pt-2.5"
        onClick={(e) => e.stopPropagation()}
      >
        <RowActions schedule={schedule} actions={actions} />
      </div>
    </div>
  );
}
