import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Loader2, Plus, RefreshCw, Upload, Workflow } from "lucide-react";
import { useCreateFlow, useDeleteFlow, useFlows, useImportFlow, useMigrateFlowDocument, useRunFlow, useToggleFlow, useUpdateFlow, useDuplicateFlow } from "./hooks";
import { MigrateFlowDialog } from "./MigrateFlowDialog";
import { useProjects } from "@/features/projects/hooks";
import { useCreateSchedule } from "@/features/schedules/hooks";
import { ScheduleFormDialog } from "@/features/schedules/ScheduleFormDialog";
import { flowNameConflicts, resolveImportTargetProjectId } from "@/lib/flowImport";
import { FlowEditDialog } from "./FlowEditDialog";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { QuickRunDialog } from "./QuickRunDialog";
import { sortRows, useSort } from "@/components/ui/SortableHeader";
import { Button } from "@/components/ui/button";
import { FilterBar, FilterField, SearchInput } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import { ViewToggle } from "@/components/filters/ViewToggle";
import type { Flow } from "@/features/flows/types";
import { CreateFlowDialog } from "./components/CreateFlowDialog";
import { ImportFlowDialog } from "./components/ImportFlowDialog";
import { FlowCard } from "./components/FlowCard";
import { FlowTable, FLOW_SORT, type FlowSortKey } from "./components/FlowTable";

type PendingAction =
  | { kind: "disable"; flow: Flow }
  | { kind: "enable"; flow: Flow }
  | { kind: "delete"; flow: Flow };

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
  const [layout, setLayout] = useLayoutPreference("flows", "cards");
  const [editingFlow, setEditingFlow] = useState<Flow | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [runFlow, setRunFlow] = useState<Flow | null>(null);
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
    // Scope the name-collision check to the destination project — the backend
    // has no global flow-name uniqueness, so a clash in a *different* project
    // must not block a valid import.
    const targetProjectId = resolveImportTargetProjectId(projectFilter, projects);
    if (flowNameConflicts(flows ?? [], name, targetProjectId)) {
      setImportNameError(`A flow named "${name}" already exists in this project. Choose a different name.`);
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
          <CreateFlowDialog
            open={open}
            onOpenChange={setOpen}
            projects={projects ?? []}
            defaultProjectId={projectFilter}
            isPending={createFlow.isPending}
            trigger={
              <Button>
                <Plus className="h-4 w-4" /> New flow
              </Button>
            }
            onCreate={(values, onSuccess) =>
              createFlow.mutate(
                {
                  name: values.name,
                  description: values.description,
                  project_id: values.projectId || undefined,
                  graph_json: values.graph,
                },
                {
                  onSuccess: (flow) => {
                    onSuccess();
                    setOpen(false);
                    navigate(`/flows/${flow.id}`);
                  },
                },
              )
            }
          />
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
                      onRun={() => { runMutation.reset(); setRunFlow(flow); }}
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
                  onRun={(flow) => { runMutation.reset(); setRunFlow(flow); }}
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

      <QuickRunDialog
        flow={runFlow}
        onOpenChange={(o) => !o && setRunFlow(null)}
        isPending={runMutation.isPending}
        error={runMutation.error}
        onRun={({ engine, parameters }) => {
          if (!runFlow) return;
          runMutation.mutate(
            { flowId: runFlow.id, engine, parameters },
            {
              onSuccess: (run) => {
                setRunFlow(null);
                navigate(`/runs/${run.id}`);
              },
            },
          );
        }}
      />

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

      <ImportFlowDialog
        open={importDialogOpen}
        onOpenChange={(o) => !o && closeImportDialog()}
        name={importName}
        onNameChange={(v) => { setImportName(v); setImportNameError(null); }}
        nameError={importNameError}
        warning={importWarning}
        error={importError}
        isPending={importFlow.isPending}
        onSubmit={handleImportConfirm}
      />

      <MigrateFlowDialog open={migrateDialogOpen} onOpenChange={setMigrateDialogOpen} />
    </div>
  );
}
