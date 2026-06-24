import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { AlertCircle, CalendarClock, LayoutGrid, List, Loader2, Pencil, Play, Plus, Power, Trash2, Workflow } from "lucide-react";
import { useCreateFlow, useDeleteFlow, useFlows, useRunFlow, useToggleFlow, useUpdateFlow } from "./hooks";
import { useProjects } from "@/features/projects/hooks";
import { useCreateSchedule } from "@/features/schedules/hooks";
import { ScheduleFormDialog } from "@/features/schedules/ScheduleFormDialog";
import { flowFormSchema, type FlowFormValues } from "@/lib/validators";
import { FlowEditDialog } from "./FlowEditDialog";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { FilterBar, FilterField, SearchInput } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { projectColor } from "@/lib/projectColors";
import type { Flow } from "@/lib/types";
import { cn } from "@/lib/utils";

type PendingAction =
  | { kind: "disable"; flow: Flow }
  | { kind: "enable"; flow: Flow }
  | { kind: "delete"; flow: Flow };

export function FlowListPage() {
  const { data: flows, isLoading } = useFlows();
  const { data: projects } = useProjects();
  const createFlow = useCreateFlow();
  const deleteFlow = useDeleteFlow();
  const toggleFlow = useToggleFlow();
  const updateFlow = useUpdateFlow();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [newFlowProjectId, setNewFlowProjectId] = useState("");
  const [layout, setLayout] = useLayoutPreference("flows", "cards");
  const [editingFlow, setEditingFlow] = useState<Flow | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [runFlow, setRunFlow] = useState<Flow | null>(null);
  const [runEngine, setRunEngine] = useState<"pandas" | "polars">("pandas");
  const runMutation = useRunFlow();
  const [schedulingFlow, setSchedulingFlow] = useState<Flow | null>(null);
  const createSchedule = useCreateSchedule();

  const projectById = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p])),
    [projects],
  );

  const filtered = useMemo(() => {
    let list = flows ?? [];
    if (projectFilter) list = list.filter((f) => f.project_id === projectFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          (f.description ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [flows, projectFilter, search]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FlowFormValues>({ defaultValues: { name: "", description: "" } });

  const onCreate = handleSubmit((values) => {
    const parsed = flowFormSchema.safeParse(values);
    if (!parsed.success) return;
    createFlow.mutate(
      {
        name: values.name,
        description: values.description,
        project_id: newFlowProjectId || undefined,
        graph_json: { nodes: [], edges: [] },
      },
      {
        onSuccess: (flow) => {
          reset();
          setOpen(false);
          navigate(`/flows/${flow.id}`);
        },
      },
    );
  });

  const handleConfirm = () => {
    if (!pendingAction) return;
    const { kind, flow } = pendingAction;
    setPendingAction(null);
    if (kind === "delete") deleteFlow.mutate(flow.id);
    else if (kind === "disable") toggleFlow.mutate({ id: flow.id, is_disabled: true });
    else toggleFlow.mutate({ id: flow.id, is_disabled: false });
  };

  const confirmTitle = pendingAction
    ? pendingAction.kind === "delete"
      ? `Delete "${pendingAction.flow.name}"?`
      : pendingAction.kind === "disable"
        ? `Disable "${pendingAction.flow.name}"?`
        : `Enable "${pendingAction.flow.name}"?`
    : "";

  const confirmDescription = pendingAction ? (
    pendingAction.kind === "delete" ? (
      <p>This will permanently delete the flow and its run history. Datasets are not affected.</p>
    ) : pendingAction.kind === "disable" ? (
      <p>
        The flow will be marked as disabled — read-only and cannot be triggered or run until
        re-enabled.
      </p>
    ) : (
      <p>The flow will be re-enabled and available for running again.</p>
    )
  ) : null;

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <Workflow className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Flows</h1>
            <p className="text-xs text-muted-foreground">
              Visual pipelines you can preview, run, and export.
            </p>
          </div>
        </div>
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (o) setNewFlowProjectId(projectFilter); }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" /> New flow
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create flow</DialogTitle>
            </DialogHeader>
            <form onSubmit={onCreate} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <Label>Name</Label>
                <Input {...register("name")} placeholder="My ETL flow" />
                {errors.name && (
                  <p className="text-[11px] text-destructive">{errors.name.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label>Description</Label>
                <Textarea {...register("description")} />
              </div>
              <div className="flex flex-col gap-1">
                <Label>Project</Label>
                <SearchableSelect
                  value={newFlowProjectId}
                  onChange={setNewFlowProjectId}
                  allLabel="No project"
                  placeholder="Search projects…"
                  options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
                />
              </div>
              <Button type="submit" disabled={createFlow.isPending}>
                {createFlow.isPending ? "Creating…" : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <FilterBar className="mb-4">
        <FilterField label="Search" className="flex-1 min-w-[10rem]">
          <SearchInput value={search} onChange={setSearch} placeholder="Search flows…" />
        </FilterField>
        <FilterField label="Project">
          <SearchableSelect
            value={projectFilter}
            onChange={setProjectFilter}
            allLabel="All projects"
            placeholder="Search projects…"
            className="sm:w-52"
            options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </FilterField>
        <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
          <button
            type="button"
            onClick={() => setLayout("cards")}
            className={cn("rounded p-1.5 transition-colors", layout === "cards" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
            title="Card view"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setLayout("table")}
            className={cn("rounded p-1.5 transition-colors", layout === "table" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
            title="Table view"
          >
            <List className="h-3.5 w-3.5" />
          </button>
        </div>
      </FilterBar>

      {(toggleFlow.isError || deleteFlow.isError) && (
        <div className="mb-4 flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {((toggleFlow.error || deleteFlow.error) as Error)?.message ?? "Operation failed. Check the console for details."}
        </div>
      )}

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      )}

      {layout === "cards" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((flow) => (
            <FlowCard
              key={flow.id}
              flow={flow}
              projectName={flow.project_id ? projectById.get(flow.project_id)?.name : undefined}
              projectColorKey={flow.project_id ? projectById.get(flow.project_id)?.color : undefined}
              onOpen={() => navigate(`/flows/${flow.id}`)}
              onEdit={() => setEditingFlow(flow)}
              onRun={() => { setRunFlow(flow); setRunEngine("pandas"); }}
              onSchedule={() => setSchedulingFlow(flow)}
              onToggle={() => setPendingAction({ kind: flow.is_disabled ? "enable" : "disable", flow })}
              onDelete={() => setPendingAction({ kind: "delete", flow })}
            />
          ))}
        </div>
      ) : (
        <FlowTable
          flows={filtered}
          projectById={projectById}
          onOpen={(id) => navigate(`/flows/${id}`)}
          onEdit={(flow) => setEditingFlow(flow)}
          onRun={(flow) => { setRunFlow(flow); setRunEngine("pandas"); }}
          onSchedule={(flow) => setSchedulingFlow(flow)}
          onToggle={(flow) => setPendingAction({ kind: flow.is_disabled ? "enable" : "disable", flow })}
          onDelete={(flow) => setPendingAction({ kind: "delete", flow })}
        />
      )}

      {!isLoading && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {search || projectFilter
            ? "No flows match your filters."
            : "No flows yet. Create one to start building."}
        </p>
      )}

      {/* Quick-run dialog */}
      <Dialog open={runFlow !== null} onOpenChange={(o) => !o && setRunFlow(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Play className="h-4 w-4 text-brand-600" />
              Run "{runFlow?.name}"
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Engine</Label>
              <div className="flex items-center gap-2 overflow-hidden rounded-md border border-input text-sm">
                {(["pandas", "polars"] as const).map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => setRunEngine(e)}
                    className={cn(
                      "flex-1 py-2 transition-colors",
                      runEngine === e
                        ? "bg-brand-600 font-medium text-white"
                        : "bg-background text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
            {runMutation.isError && (
              <p className="flex items-center gap-1.5 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {(runMutation.error as Error)?.message ?? "Run failed"}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRunFlow(null)}>Cancel</Button>
              <Button
                onClick={() => {
                  if (!runFlow) return;
                  runMutation.mutate(
                    { flowId: runFlow.id, engine: runEngine },
                    {
                      onSuccess: (run) => {
                        setRunFlow(null);
                        navigate(`/runs/${run.id}`);
                      },
                    },
                  );
                }}
                disabled={runMutation.isPending}
              >
                {runMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ScheduleFormDialog
        open={schedulingFlow !== null}
        onOpenChange={(o) => !o && setSchedulingFlow(null)}
        lockedFlowId={schedulingFlow?.id}
        submitting={createSchedule.isPending}
        error={createSchedule.error}
        onSubmit={(flowId, body) =>
          createSchedule.mutate(
            { flowId, body },
            { onSuccess: (schedule) => { setSchedulingFlow(null); navigate(`/schedules/${schedule.id}`); } },
          )
        }
      />

      <FlowEditDialog
        open={editingFlow !== null}
        onOpenChange={(o) => !o && setEditingFlow(null)}
        flow={editingFlow}
        submitting={updateFlow.isPending}
        error={updateFlow.error}
        onSubmit={(values) =>
          editingFlow &&
          updateFlow.mutate(
            { id: editingFlow.id, body: { name: values.name, description: values.description } },
            { onSuccess: () => setEditingFlow(null) },
          )
        }
      />

      <ConfirmDialog
        open={pendingAction !== null}
        onOpenChange={(o) => !o && setPendingAction(null)}
        title={confirmTitle}
        description={confirmDescription}
        confirmLabel={
          pendingAction?.kind === "delete"
            ? "Delete"
            : pendingAction?.kind === "disable"
              ? "Disable"
              : "Enable"
        }
        variant={pendingAction?.kind === "delete" ? "destructive" : "warning"}
        isPending={deleteFlow.isPending || toggleFlow.isPending}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

function FlowCard({
  flow,
  projectName,
  projectColorKey,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
}: {
  flow: Flow;
  projectName?: string;
  projectColorKey?: string;
  onOpen: () => void;
  onEdit: () => void;
  onRun: () => void;
  onSchedule: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const theme = projectColor(projectColorKey);
  const fmt = useFormatDateTime();
  return (
    <div className={cn("group animate-fade-in-up flex flex-col rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md", flow.is_disabled ? "border-amber-300 opacity-70" : "border-border")}>
      <button onClick={onOpen} className="flex-1 text-left">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-brand-600" />
          <span className="truncate font-semibold">{flow.name}</span>
          {flow.is_disabled && (
            <span className="shrink-0 rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
              disabled
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
          {flow.description || "No description"}
        </p>
        <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{flow.graph_json?.nodes.length ?? 0} nodes</span>
          {projectName && (
            <span className="flex items-center gap-1.5">
              <span className={cn("h-2 w-2 rounded-full", theme.dot)} />
              {projectName}
            </span>
          )}
        </div>
        <div className="mt-1.5 text-[11px] text-muted-foreground/80">
          Created {fmt(flow.created_at)}
          {" · "}
          {flow.last_run_at ? `last run ${fmt(flow.last_run_at)}` : "never run"}
        </div>
      </button>
      <div className="mt-3 flex items-center justify-end gap-2 border-t border-border pt-2.5">
        <Button size="sm" variant="outline" onClick={onOpen}>
          Open
        </Button>
        <button
          onClick={onRun}
          disabled={flow.is_disabled}
          className="rounded-md p-2 text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700 disabled:pointer-events-none disabled:opacity-40"
          title="Run flow"
        >
          <Play className="h-4 w-4" />
        </button>
        <button
          onClick={onSchedule}
          disabled={flow.is_disabled}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          title="Schedule flow"
        >
          <CalendarClock className="h-4 w-4" />
        </button>
        <button
          onClick={onEdit}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Edit name & description"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          onClick={onToggle}
          className={cn(
            "rounded-md p-2 transition-colors hover:bg-muted",
            flow.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
          )}
          title={flow.is_disabled ? "Enable flow" : "Disable flow"}
        >
          <Power className="h-4 w-4" />
        </button>
        <button
          onClick={onDelete}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          title="Delete flow"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function FlowTable({
  flows,
  projectById,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
}: {
  flows: Flow[];
  projectById: Map<string, { name: string; color: string }>;
  onOpen: (id: string) => void;
  onEdit: (flow: Flow) => void;
  onRun: (flow: Flow) => void;
  onSchedule: (flow: Flow) => void;
  onToggle: (flow: Flow) => void;
  onDelete: (flow: Flow) => void;
}) {
  const fmt = useFormatDateTime();
  if (flows.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 text-left font-semibold">Name</th>
            <th className="px-4 py-2.5 text-left font-semibold">Project</th>
            <th className="px-4 py-2.5 text-left font-semibold">Nodes</th>
            <th className="px-4 py-2.5 text-left font-semibold">Status</th>
            <th className="px-4 py-2.5 text-left font-semibold">Created</th>
            <th className="px-4 py-2.5 text-left font-semibold">Last run</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {flows.map((flow) => {
            const proj = flow.project_id ? projectById.get(flow.project_id) : undefined;
            const theme = projectColor(proj?.color);
            return (
              <tr
                key={flow.id}
                className={cn("border-t border-border hover:bg-accent/40 transition-colors", flow.is_disabled && "bg-amber-50/30 opacity-70")}
              >
                <td className="px-4 py-2.5">
                  <button onClick={() => onOpen(flow.id)} className="font-medium hover:underline">
                    {flow.name}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {proj ? (
                    <span className="flex items-center gap-1.5">
                      <span className={cn("h-2 w-2 rounded-full", theme.dot)} />
                      {proj.name}
                    </span>
                  ) : "—"}
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {flow.graph_json?.nodes.length ?? 0}
                </td>
                <td className="px-4 py-2.5">
                  {flow.is_disabled ? (
                    <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                      disabled
                    </span>
                  ) : (
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                      active
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">{fmt(flow.created_at)}</td>
                <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                  {flow.last_run_at ? fmt(flow.last_run_at) : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onRun(flow)}
                      disabled={flow.is_disabled}
                      className="rounded-md p-1.5 text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700 disabled:pointer-events-none disabled:opacity-40"
                      title="Run flow"
                    >
                      <Play className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onSchedule(flow)}
                      disabled={flow.is_disabled}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      title="Schedule flow"
                    >
                      <CalendarClock className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onEdit(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      title="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onToggle(flow)}
                      className={cn(
                        "rounded-md p-1.5 transition-colors hover:bg-muted",
                        flow.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
                      )}
                      title={flow.is_disabled ? "Enable" : "Disable"}
                    >
                      <Power className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onDelete(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
