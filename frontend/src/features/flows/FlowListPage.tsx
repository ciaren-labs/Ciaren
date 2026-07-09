import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { AlertCircle, CalendarClock, Copy as CopyIcon, FileText, Loader2, Pencil, Play, Plus, Power, RefreshCw, Trash2, Upload, Workflow } from "lucide-react";
import { useCreateFlow, useDeleteFlow, useFlows, useImportFlow, useMigrateFlowDocument, useRunFlow, useToggleFlow, useUpdateFlow, useDuplicateFlow } from "./hooks";
import { MigrateFlowDialog } from "./MigrateFlowDialog";
import { FLOW_TEMPLATES, buildTemplateGraph } from "@/lib/flowTemplates";
import { useProjects } from "@/features/projects/hooks";
import { useCreateSchedule } from "@/features/schedules/hooks";
import { ScheduleFormDialog } from "@/features/schedules/ScheduleFormDialog";
import { flowFormSchema, type FlowFormValues } from "@/lib/validators";
import { FlowEditDialog } from "./FlowEditDialog";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { friendlyErrorMessage } from "@/lib/errors";
import { SortableTh, sortRows, useSort, type SortState } from "@/components/ui/SortableHeader";
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
import { ViewToggle } from "@/components/filters/ViewToggle";
import { ENGINES, type Engine, type Flow } from "@/lib/types";
import { cn } from "@/lib/utils";

type PendingAction =
  | { kind: "disable"; flow: Flow }
  | { kind: "enable"; flow: Flow }
  | { kind: "delete"; flow: Flow };


type FlowSortKey = "name" | "nodes" | "status" | "created" | "last_run";
const FLOW_SORT: Record<FlowSortKey, (f: Flow) => string | number | null> = {
  name: (f) => f.name.toLowerCase(),
  nodes: (f) => f.graph_json?.nodes?.length ?? 0,
  status: (f) => (f.is_disabled ? "disabled" : "active"),
  created: (f) => f.created_at,
  last_run: (f) => f.last_run_at ?? null,
};

export function FlowListPage() {
  const { data: flows, isPending, isError, error, refetch } = useFlows();
  const { data: projects } = useProjects();
  const createFlow = useCreateFlow();
  const deleteFlow = useDeleteFlow();
  const duplicateFlow = useDuplicateFlow();
  const toggleFlow = useToggleFlow();
  const updateFlow = useUpdateFlow();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  // A single useDuplicateFlow() instance is shared across every row, so its
  // own isPending/variables only ever reflect the most recently *invoked*
  // call — duplicating flow B while flow A's request is still in flight would
  // otherwise make A's row look finished (and let a same-flow re-click race
  // past the double-submit guard below). Tracking in-flight ids locally keeps
  // each row's pending state independent of the others.
  const [duplicatingIds, setDuplicatingIds] = useState<Set<string>>(new Set());
  const handleDuplicate = (flow: Flow) => {
    if (duplicatingIds.has(flow.id)) return;
    setDuplicatingIds((prev) => new Set(prev).add(flow.id));
    // mutateAsync's returned promise is tied to this specific call's own
    // execution, unlike the shared observer's isPending/variables — so it
    // still settles correctly here even if another row starts duplicating
    // (and the observer moves on) before this one finishes. The error itself
    // is already surfaced by the global mutation-cache toast; swallow it here
    // so it doesn't also become an unhandled rejection.
    duplicateFlow
      .mutateAsync(flow.id)
      .catch(() => {})
      .finally(() => {
        setDuplicatingIds((prev) => {
          const next = new Set(prev);
          next.delete(flow.id);
          return next;
        });
      });
  };
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [newFlowProjectId, setNewFlowProjectId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [layout, setLayout] = useLayoutPreference("flows", "cards");
  const [editingFlow, setEditingFlow] = useState<Flow | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [runFlow, setRunFlow] = useState<Flow | null>(null);
  const [runEngine, setRunEngine] = useState<Engine>("pandas");
  const runMutation = useRunFlow();
  const [schedulingFlow, setSchedulingFlow] = useState<Flow | null>(null);
  const createSchedule = useCreateSchedule();
  const importFlow = useImportFlow();
  const migrateCheck = useMigrateFlowDocument();
  const importInputRef = useRef<HTMLInputElement>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importWarning, setImportWarning] = useState<string | null>(null);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [pendingImportDoc, setPendingImportDoc] = useState<Record<string, unknown> | null>(null);
  const [importName, setImportName] = useState("");
  const [importNameError, setImportNameError] = useState<string | null>(null);
  const [migrateDialogOpen, setMigrateDialogOpen] = useState(false);

  const onImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-importing the same file
    if (!file) return;
    setImportError(null);
    setImportWarning(null);
    let doc: Record<string, unknown>;
    try {
      doc = JSON.parse(await file.text()) as Record<string, unknown>;
    } catch {
      setImportError("That file isn't valid JSON.");
      return;
    }
    if (!doc || typeof doc !== "object" || (!("graph_json" in doc) && !("graph" in doc))) {
      setImportError("Not a flow document — expected a 'graph_json' or 'graph' field.");
      return;
    }
    const defaultName =
      typeof doc.name === "string" && doc.name.trim() ? doc.name.trim() : "Imported flow";
    setPendingImportDoc(doc);
    setImportName(defaultName);
    setImportNameError(null);
    setImportDialogOpen(true);
    // Best-effort dry-run check, purely for the informational warning below —
    // the real /flows/import call is the source of truth and migrates
    // automatically regardless, so failures here are silently ignored.
    migrateCheck.mutate(doc, {
      onSuccess: (res) => {
        if (res.migrated) {
          setImportWarning(
            `This file uses an older format (schema v${res.from_version}) and will be upgraded to v${res.to_version} automatically.`,
          );
        }
      },
      onError: () => {},
    });
  };

  const handleImportConfirm = () => {
    if (!pendingImportDoc) return;
    const name = importName.trim();
    if (!name) {
      setImportNameError("Name is required.");
      return;
    }
    const conflict = (flows ?? []).some((f) => f.name.toLowerCase() === name.toLowerCase());
    if (conflict) {
      setImportNameError(`A flow named "${name}" already exists. Choose a different name.`);
      return;
    }
    const payload = {
      ...pendingImportDoc,
      name,
      project_id: projectFilter || undefined,
    } as Parameters<typeof importFlow.mutate>[0];
    importFlow.mutate(payload, {
      onSuccess: (flow) => {
        setImportDialogOpen(false);
        setPendingImportDoc(null);
        navigate(`/flows/${flow.id}`);
      },
      onError: (err) => setImportError((err as Error)?.message ?? "Import failed."),
    });
  };

  const closeImportDialog = () => {
    setImportDialogOpen(false);
    setPendingImportDoc(null);
    setImportName("");
    setImportNameError(null);
    setImportWarning(null);
  };

  const { sort, toggle: toggleSort } = useSort<FlowSortKey>("created", "desc");

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

  // Group flows by project (insertion order), sorting each group's rows by the
  // active sort column. Both card and table views share this.
  const groups = useMemo(() => {
    const map = new Map<string, Flow[]>();
    for (const f of filtered) {
      const pid = f.project_id ?? "";
      const arr = map.get(pid);
      if (arr) arr.push(f);
      else map.set(pid, [f]);
    }
    return [...map.entries()].map(
      ([pid, items]) => [pid, sortRows(items, sort, FLOW_SORT)] as const,
    );
  }, [filtered, sort]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FlowFormValues>({ defaultValues: { name: "", description: "" } });

  const onCreate = handleSubmit((values) => {
    const parsed = flowFormSchema.safeParse(values);
    if (!parsed.success) return;
    const template = FLOW_TEMPLATES.find((t) => t.id === selectedTemplateId);
    createFlow.mutate(
      {
        name: values.name,
        description: values.description,
        project_id: newFlowProjectId || undefined,
        graph_json: template ? buildTemplateGraph(template) : { nodes: [], edges: [] },
      },
      {
        onSuccess: (flow) => {
          reset();
          setSelectedTemplateId(null);
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
        <div className="flex items-center gap-2">
          <ViewToggle value={layout} onChange={setLayout} />
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={onImportFile}
          />
          <Button
            variant="outline"
            onClick={() => importInputRef.current?.click()}
            disabled={importFlow.isPending}
            title={
              projectFilter
                ? `Import a flow into ${projectById.get(projectFilter)?.name ?? "this project"}`
                : "Import a flow from an exported .flow.json (lands in the Default project)"
            }
          >
            {importFlow.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Import
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMigrateDialogOpen(true)}
            title="Upgrade an exported .flow.json to the current format without importing it"
          >
            <RefreshCw className="h-4 w-4" /> Migrate a file…
          </Button>
          <Dialog
            open={open}
            onOpenChange={(o) => {
              setOpen(o);
              if (o) setNewFlowProjectId(projectFilter);
              else setSelectedTemplateId(null);
            }}
          >
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
                <Label>Start from</Label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedTemplateId(null)}
                    className={cn(
                      "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
                      selectedTemplateId === null
                        ? "border-primary bg-accent"
                        : "border-input hover:bg-muted",
                    )}
                  >
                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span>
                      <span className="block text-xs font-medium">Blank flow</span>
                      <span className="block text-[11px] text-muted-foreground">
                        Start with an empty canvas.
                      </span>
                    </span>
                  </button>
                  {FLOW_TEMPLATES.map((tpl) => {
                    const Icon = tpl.icon;
                    const active = selectedTemplateId === tpl.id;
                    return (
                      <button
                        key={tpl.id}
                        type="button"
                        onClick={() => setSelectedTemplateId(tpl.id)}
                        className={cn(
                          "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
                          active ? "border-primary bg-accent" : "border-input hover:bg-muted",
                        )}
                      >
                        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>
                          <span className="block text-xs font-medium">{tpl.name}</span>
                          <span className="block text-[11px] text-muted-foreground">
                            {tpl.description}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
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
                  allLabel="Default project"
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
      </FilterBar>

      {importError && (
        <div className="mb-4 flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {importError}
        </div>
      )}

      {isPending && <LoadingState label="Loading flows…" />}
      {isError && <ErrorState error={error} title="Couldn't load flows" onRetry={() => refetch()} />}

      <div className="flex flex-col gap-4">
        {groups.map(([pid, group]) => {
          const proj = projectById.get(pid);
          return (
            <CollapsibleSection
              key={pid}
              title={proj?.name ?? "Unknown project"}
              colorKey={proj?.color}
              count={group.length}
            >
              {layout === "cards" ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {group.map((flow) => (
                    <FlowCard
                      key={flow.id}
                      flow={flow}
                      isDuplicating={duplicatingIds.has(flow.id)}
                      onOpen={() => navigate(`/flows/${flow.id}`)}
                      onEdit={() => setEditingFlow(flow)}
                      onRun={() => { setRunFlow(flow); setRunEngine(flow.graph_json?.engine ?? "pandas"); }}
                      onSchedule={() => setSchedulingFlow(flow)}
                      onToggle={() => setPendingAction({ kind: flow.is_disabled ? "enable" : "disable", flow })}
                      onDelete={() => setPendingAction({ kind: "delete", flow })}
                      onDuplicate={() => handleDuplicate(flow)}
                    />
                  ))}
                </div>
              ) : (
                <FlowTable
                  flows={group}
                  sort={sort}
                  onSort={toggleSort}
                  isDuplicating={(flow) => duplicatingIds.has(flow.id)}
                  onOpen={(id) => navigate(`/flows/${id}`)}
                  onEdit={(flow) => setEditingFlow(flow)}
                  onRun={(flow) => { setRunFlow(flow); setRunEngine(flow.graph_json?.engine ?? "pandas"); }}
                  onSchedule={(flow) => setSchedulingFlow(flow)}
                  onToggle={(flow) => setPendingAction({ kind: flow.is_disabled ? "enable" : "disable", flow })}
                  onDelete={(flow) => setPendingAction({ kind: "delete", flow })}
                  onDuplicate={handleDuplicate}
                />
              )}
            </CollapsibleSection>
          );
        })}
      </div>

      {!isPending && !isError && filtered.length === 0 && (
        search || projectFilter ? (
          <EmptyState
            icon={Workflow}
            title="No flows match your filters"
            description="Try a different search, or clear the project filter."
            action={
              <Button variant="outline" size="sm" onClick={() => { setSearch(""); setProjectFilter(""); }}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={Workflow}
            title="Build your first flow"
            description="A flow is a visual pipeline: load a dataset, add transformations, and run it — no code required."
            action={
              <Button onClick={() => setOpen(true)}>
                <Plus className="h-4 w-4" /> New flow
              </Button>
            }
          />
        )
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
                {ENGINES.map((e) => (
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
                {friendlyErrorMessage(runMutation.error, "The run couldn't be started.")}
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

      {/* Import name confirmation dialog */}
      <Dialog open={importDialogOpen} onOpenChange={(o) => !o && closeImportDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import flow</DialogTitle>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => { e.preventDefault(); handleImportConfirm(); }}
          >
            <div className="flex flex-col gap-1">
              <Label>Name</Label>
              <Input
                value={importName}
                onChange={(e) => { setImportName(e.target.value); setImportNameError(null); }}
                placeholder="Flow name"
                autoFocus
              />
              {importNameError && (
                <p className="text-[11px] text-destructive">{importNameError}</p>
              )}
            </div>
            {importWarning && !importError && (
              <p className="text-[11px] text-amber-600">{importWarning}</p>
            )}
            {importError && (
              <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-[11px] text-destructive">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {importError}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={closeImportDialog}>
                Cancel
              </Button>
              <Button type="submit" disabled={importFlow.isPending}>
                {importFlow.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Import
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <MigrateFlowDialog open={migrateDialogOpen} onOpenChange={setMigrateDialogOpen} />
    </div>
  );
}

function FlowCard({
  flow,
  isDuplicating,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
  onDuplicate,
}: {
  flow: Flow;
  isDuplicating: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onRun: () => void;
  onSchedule: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
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
          <span>{flow.graph_json?.nodes?.length ?? 0} nodes</span>
        </div>
        <div className="mt-1.5 flex flex-col gap-0.5 text-[11px] text-muted-foreground/80">
          <span>Created {fmt(flow.created_at)}</span>
          <span>{flow.last_run_at ? `Last run ${fmt(flow.last_run_at)}` : "Never run"}</span>
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
          onClick={onDuplicate}
          disabled={isDuplicating}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          title="Duplicate flow (graph, parameters and engine — not schedules or history)"
        >
          {isDuplicating ? <Loader2 className="h-4 w-4 animate-spin" /> : <CopyIcon className="h-4 w-4" />}
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
  sort,
  onSort,
  isDuplicating,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
  onDuplicate,
}: {
  flows: Flow[];
  sort: SortState<FlowSortKey>;
  onSort: (key: FlowSortKey) => void;
  isDuplicating: (flow: Flow) => boolean;
  onOpen: (id: string) => void;
  onEdit: (flow: Flow) => void;
  onRun: (flow: Flow) => void;
  onSchedule: (flow: Flow) => void;
  onToggle: (flow: Flow) => void;
  onDelete: (flow: Flow) => void;
  onDuplicate: (flow: Flow) => void;
}) {
  const fmt = useFormatDateTime();
  if (flows.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <SortableTh label="Name" sortKey="name" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Nodes" sortKey="nodes" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Status" sortKey="status" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Created" sortKey="created" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Last run" sortKey="last_run" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {flows.map((flow) => {
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
                  {flow.graph_json?.nodes?.length ?? 0}
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
                      onClick={() => onDuplicate(flow)}
                      disabled={isDuplicating(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      title="Duplicate"
                    >
                      {isDuplicating(flow) ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <CopyIcon className="h-3.5 w-3.5" />
                      )}
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
