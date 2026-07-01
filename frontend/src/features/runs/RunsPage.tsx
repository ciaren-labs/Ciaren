import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  History,
  MousePointerClick,
  RotateCcw,
  SquarePen,
} from "lucide-react";
import { useRetryRun, useRuns } from "./hooks";
import { useFlows } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { useProjects } from "@/features/projects/hooks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/PageState";
import { FilterBar, FilterField } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { ViewToggle } from "@/components/filters/ViewToggle";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { SortableTh } from "@/components/ui/SortableHeader";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { formatDuration } from "@/lib/format";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import type { RunListFilters, RunStatus, FlowRunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const DATE_CLASS =
  "h-10 rounded-md border border-input bg-background px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const STATUSES: RunStatus[] = ["success", "failed", "running", "pending"];
const PAGE_SIZE = 25;

/** Dataset cell label: a single name, or "first +N" for multi-input runs. */
function datasetLabel(run: FlowRunSummary, datasetName: Map<string, string>): string {
  const inputs = run.input_datasets?.length
    ? run.input_datasets.map((d) => d.dataset_id)
    : run.input_dataset_id
      ? [run.input_dataset_id]
      : [];
  if (inputs.length === 0) return "—";
  const first = datasetName.get(inputs[0]) ?? "—";
  return inputs.length > 1 ? `${first} +${inputs.length - 1}` : first;
}

type SortField = "created_at" | "started_at" | "status";

/** How a run was triggered. Scheduled runs link back to their schedule. */
function TriggerBadge({ run }: { run: FlowRunSummary }) {
  const navigate = useNavigate();
  if (run.trigger === "schedule") {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (run.schedule_id) navigate(`/schedules/${run.schedule_id}`);
        }}
        disabled={!run.schedule_id}
        className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 transition-colors hover:bg-brand-100 disabled:pointer-events-none"
        title={run.schedule_id ? "View schedule" : "Scheduled run"}
      >
        <CalendarClock className="h-3 w-3" /> Schedule
      </button>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
      <MousePointerClick className="h-3 w-3" /> Manual
    </span>
  );
}

export function RunsPage() {
  const navigate = useNavigate();
  const fmt = useFormatDateTime();
  const retry = useRetryRun();

  const handleRetry = (run: FlowRunSummary) => {
    if (!confirm("Re-run this flow with the same config? This creates a new run (a new run id) — the current one is kept.")) return;
    retry.mutate(run.id, { onSuccess: (created) => navigate(`/runs/${created.id}`) });
  };
  const { data: flows } = useFlows();
  const { data: datasets } = useDatasets();
  const { data: projects } = useProjects();

  const [flowId, setFlowId] = useState("");
  const [status, setStatus] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [layout, setLayout] = useLayoutPreference("runs", "table");

  const filters: RunListFilters = useMemo(
    () => ({
      flow_id: flowId || undefined,
      status: (status || undefined) as RunStatus | undefined,
      dataset_id: datasetId || undefined,
      project_id: projectId || undefined,
      started_after: after ? `${after}T00:00:00` : undefined,
      started_before: before ? `${before}T23:59:59` : undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [flowId, status, datasetId, projectId, after, before, sortBy, sortOrder, page],
  );

  const { data: runs, isLoading, isError, error, refetch } = useRuns(filters);

  const flowName = useMemo(
    () => new Map((flows ?? []).map((f) => [f.id, f.name])),
    [flows],
  );
  const datasetName = useMemo(
    () => new Map((datasets ?? []).map((d) => [d.id, d.name])),
    [datasets],
  );
  const projectById = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p])),
    [projects],
  );

  // Group the current page's runs into per-project sections, keeping the (already
  // sorted) run order within each. Insertion order = first appearance.
  const runGroups = useMemo(() => {
    const groups = new Map<string, FlowRunSummary[]>();
    for (const run of runs ?? []) {
      const pid = run.project_id ?? "";
      const arr = groups.get(pid);
      if (arr) arr.push(run);
      else groups.set(pid, [run]);
    }
    return [...groups.entries()];
  }, [runs]);

  const hasFilters = flowId || status || datasetId || projectId || after || before;
  const reset = () => {
    setFlowId("");
    setStatus("");
    setDatasetId("");
    setProjectId("");
    setAfter("");
    setBefore("");
    setPage(0);
  };

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(0);
  };

  const hasMore = (runs?.length ?? 0) === PAGE_SIZE;
  const isEmpty = !runs || runs.length === 0;

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <History className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Run history</h1>
            <p className="text-xs text-muted-foreground">
              Every flow execution, newest first. Click a run to inspect its results.
            </p>
          </div>
        </div>
        <ViewToggle value={layout} onChange={setLayout} />
      </div>

      {/* Filter bar */}
      <FilterBar className="mb-4">
        <FilterField label="Flow">
          <SearchableSelect
            value={flowId}
            onChange={(v) => { setFlowId(v); setPage(0); }}
            allLabel="All flows"
            placeholder="Search flows…"
            options={(flows ?? []).map((f) => ({ value: f.id, label: f.name }))}
          />
        </FilterField>
        <FilterField label="Project">
          <SearchableSelect
            value={projectId}
            onChange={(v) => { setProjectId(v); setPage(0); }}
            allLabel="All projects"
            placeholder="Search projects…"
            options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </FilterField>
        <FilterField label="Dataset">
          <SearchableSelect
            value={datasetId}
            onChange={(v) => { setDatasetId(v); setPage(0); }}
            allLabel="All datasets"
            placeholder="Search datasets…"
            options={(datasets ?? []).map((d) => ({ value: d.id, label: d.name }))}
          />
        </FilterField>
        <FilterField label="Status" className="min-w-[8rem]">
          <SearchableSelect
            value={status}
            onChange={(v) => { setStatus(v); setPage(0); }}
            allLabel="Any status"
            placeholder="Search status…"
            options={STATUSES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
          />
        </FilterField>
        <FilterField label="From" className="min-w-[8rem]">
          <input
            type="date"
            className={DATE_CLASS}
            value={after}
            onChange={(e) => { setAfter(e.target.value); setPage(0); }}
          />
        </FilterField>
        <FilterField label="To" className="min-w-[8rem]">
          <input
            type="date"
            className={DATE_CLASS}
            value={before}
            onChange={(e) => { setBefore(e.target.value); setPage(0); }}
          />
        </FilterField>
        {hasFilters && (
          <button
            onClick={reset}
            className="flex h-10 self-end items-center gap-1.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Clear
          </button>
        )}
      </FilterBar>

      {isLoading ? (
        <LoadingState label="Loading runs…" />
      ) : isError ? (
        <ErrorState error={error} title="Couldn't load runs" onRetry={() => refetch()} />
      ) : !isEmpty ? (
        <>
          {layout === "table" ? (
            <div className="flex flex-col gap-4">
              {runGroups.map(([pid, group]) => {
                const proj = projectById.get(pid);
                return (
                  <CollapsibleSection
                    key={pid}
                    title={proj?.name ?? "Unknown project"}
                    colorKey={proj?.color}
                    count={group.length}
                  >
                    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                          <tr>
                            <th className="px-4 py-2.5 text-left font-semibold">Flow</th>
                            <SortableTh label="Status" sortKey="status" sort={{ key: sortBy, dir: sortOrder }} onSort={handleSort} className="px-4 py-2.5 text-left" />
                            <th className="px-4 py-2.5 text-left font-semibold">Trigger</th>
                            <th className="px-4 py-2.5 text-left font-semibold">Dataset</th>
                            <SortableTh label="Started" sortKey="created_at" sort={{ key: sortBy, dir: sortOrder }} onSort={handleSort} className="px-4 py-2.5 text-left" />
                            <th className="px-4 py-2.5 text-left font-semibold">Duration</th>
                            <th className="px-4 py-2.5 text-right font-semibold sr-only">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.map((run) => (
                            <RunRow
                              key={run.id}
                              run={run}
                              flowName={flowName}
                              datasetName={datasetName}
                              fmt={fmt}
                              onClick={() => navigate(`/runs/${run.id}`)}
                              onOpenFlow={() => navigate(`/flows/${run.flow_id}`)}
                              onRetry={() => handleRetry(run)}
                              retrying={retry.isPending}
                            />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CollapsibleSection>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {runGroups.map(([pid, group]) => {
                const proj = projectById.get(pid);
                return (
                  <CollapsibleSection
                    key={pid}
                    title={proj?.name ?? "Unknown project"}
                    colorKey={proj?.color}
                    count={group.length}
                  >
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {group.map((run) => (
                        <RunCard
                          key={run.id}
                          run={run}
                          flowName={flowName}
                          datasetName={datasetName}
                          fmt={fmt}
                          onClick={() => navigate(`/runs/${run.id}`)}
                          onOpenFlow={() => navigate(`/flows/${run.flow_id}`)}
                          onRetry={() => handleRetry(run)}
                          retrying={retry.isPending}
                        />
                      ))}
                    </div>
                  </CollapsibleSection>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Page {page + 1} · {runs!.length} run{runs!.length !== 1 ? "s" : ""}
            </span>
            <div className="flex items-center gap-1">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="flex items-center gap-1 rounded-md px-2 py-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Prev
              </button>
              <button
                disabled={!hasMore}
                onClick={() => setPage((p) => p + 1)}
                className="flex items-center gap-1 rounded-md px-2 py-1 transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </>
      ) : hasFilters ? (
        <EmptyState
          icon={History}
          title="No runs match these filters"
          description="Try widening the date range, or clear the filters."
          action={
            <Button variant="outline" size="sm" onClick={reset}>
              Clear filters
            </Button>
          }
        />
      ) : (
        <EmptyState
          icon={History}
          title="No runs yet"
          description="Run a flow and every execution shows up here, with its status, duration, and results."
          action={
            <Button variant="outline" size="sm" onClick={() => navigate("/flows")}>
              Go to flows
            </Button>
          }
        />
      )}
    </div>
  );
}

function RunRow({
  run,
  flowName,
  datasetName,
  fmt,
  onClick,
  onOpenFlow,
  onRetry,
  retrying,
}: {
  run: FlowRunSummary;
  flowName: Map<string, string>;
  datasetName: Map<string, string>;
  fmt: (iso: string | null | undefined) => string;
  onClick: () => void;
  onOpenFlow: () => void;
  onRetry: () => void;
  retrying: boolean;
}) {
  return (
    <tr
      onClick={onClick}
      className="cursor-pointer border-t border-border transition-colors hover:bg-accent/40"
    >
      <td className="px-4 py-2.5 font-medium">
        {run.flow_name ?? flowName.get(run.flow_id) ?? "—"}
      </td>
      <td className="px-4 py-2.5">
        <StatusBadge status={run.status} />
      </td>
      <td className="px-4 py-2.5">
        <TriggerBadge run={run} />
      </td>
      <td className="px-4 py-2.5 text-muted-foreground">
        {datasetLabel(run, datasetName)}
      </td>
      <td className="px-4 py-2.5 text-muted-foreground">{fmt(run.created_at)}</td>
      <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
        {formatDuration(run.started_at, run.finished_at)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <div className="flex items-center justify-end gap-1">
          {run.status === "failed" && (
            <button
              onClick={(e) => { e.stopPropagation(); onRetry(); }}
              disabled={retrying}
              title="Re-run the flow with the same config (creates a new run)"
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            >
              <RotateCcw className={cn("h-3.5 w-3.5", retrying && "animate-spin")} /> Retry
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onOpenFlow(); }}
            title="Open the flow in the editor"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <SquarePen className="h-3.5 w-3.5" /> Flow
          </button>
        </div>
      </td>
    </tr>
  );
}

function RunCard({
  run,
  flowName,
  datasetName,
  fmt,
  onClick,
  onOpenFlow,
  onRetry,
  retrying,
}: {
  run: FlowRunSummary;
  flowName: Map<string, string>;
  datasetName: Map<string, string>;
  fmt: (iso: string | null | undefined) => string;
  onClick: () => void;
  onOpenFlow: () => void;
  onRetry: () => void;
  retrying: boolean;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter") onClick(); }}
      className="animate-fade-in-up flex cursor-pointer flex-col gap-2 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold leading-tight">
          {run.flow_name ?? flowName.get(run.flow_id) ?? "—"}
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          <TriggerBadge run={run} />
          <StatusBadge status={run.status} />
        </div>
      </div>
      {(run.input_datasets?.length || run.input_dataset_id) && (
        <span className="text-xs text-muted-foreground">
          {datasetLabel(run, datasetName)}
        </span>
      )}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{fmt(run.created_at)}</span>
        <span className="tabular-nums">{formatDuration(run.started_at, run.finished_at)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onOpenFlow(); }}
          title="Open the flow in the editor"
          className="inline-flex w-fit items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <SquarePen className="h-3.5 w-3.5" /> Open flow
        </button>
        {run.status === "failed" && (
          <button
            onClick={(e) => { e.stopPropagation(); onRetry(); }}
            disabled={retrying}
            title="Re-run the flow with the same config (creates a new run)"
            className="inline-flex w-fit items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", retrying && "animate-spin")} /> Retry
          </button>
        )}
      </div>
    </div>
  );
}
