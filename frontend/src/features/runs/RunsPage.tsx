import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
  History,
  LayoutGrid,
  List,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { useRuns } from "./hooks";
import { useFlows } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { useProjects } from "@/features/projects/hooks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FilterBar, FilterField } from "@/components/filters/FilterBar";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { formatDuration } from "@/lib/format";
import { projectColor } from "@/lib/projectColors";
import { useLayoutPreference } from "@/lib/useLayoutPreference";
import type { RunListFilters, RunStatus, FlowRunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const DATE_CLASS =
  "h-10 rounded-md border border-input bg-background px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const STATUSES: RunStatus[] = ["success", "failed", "running", "pending"];
const PAGE_SIZE = 25;

type SortField = "created_at" | "started_at" | "status";

export function RunsPage() {
  const navigate = useNavigate();
  const fmt = useFormatDateTime();
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

  const { data: runs, isLoading } = useRuns(filters);

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
    <div className="mx-auto max-w-6xl p-6">
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
        <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
          <button
            type="button"
            onClick={() => setLayout("table")}
            className={cn("rounded p-1.5 transition-colors", layout === "table" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
            title="Table view"
          >
            <List className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setLayout("cards")}
            className={cn("rounded p-1.5 transition-colors", layout === "cards" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
            title="Card view"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </button>
        </div>
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
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading runs…
        </p>
      ) : !isEmpty ? (
        <>
          {layout === "table" ? (
            <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-semibold">Flow</th>
                    <th className="px-4 py-2.5 text-left font-semibold">Project</th>
                    <th className="px-4 py-2.5 text-left font-semibold">
                      <SortHeader field="status" current={sortBy} order={sortOrder} onSort={handleSort}>
                        Status
                      </SortHeader>
                    </th>
                    <th className="px-4 py-2.5 text-left font-semibold">Dataset</th>
                    <th className="px-4 py-2.5 text-left font-semibold">
                      <SortHeader field="created_at" current={sortBy} order={sortOrder} onSort={handleSort}>
                        Started
                      </SortHeader>
                    </th>
                    <th className="px-4 py-2.5 text-left font-semibold">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {runs!.map((run) => (
                    <RunRow
                      key={run.id}
                      run={run}
                      flowName={flowName}
                      datasetName={datasetName}
                      projectById={projectById}
                      fmt={fmt}
                      onClick={() => navigate(`/runs/${run.id}`)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {runs!.map((run) => (
                <RunCard
                  key={run.id}
                  run={run}
                  flowName={flowName}
                  datasetName={datasetName}
                  projectById={projectById}
                  fmt={fmt}
                  onClick={() => navigate(`/runs/${run.id}`)}
                />
              ))}
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
      ) : (
        <div className="rounded-xl border border-dashed border-border p-10 text-center">
          <p className="text-sm text-muted-foreground">
            {hasFilters
              ? "No runs match these filters."
              : "No runs yet. Execute a flow to see its history here."}
          </p>
        </div>
      )}
    </div>
  );
}

function SortHeader({
  field,
  current,
  order,
  onSort,
  children,
}: {
  field: SortField;
  current: SortField;
  order: "asc" | "desc";
  onSort: (f: SortField) => void;
  children: React.ReactNode;
}) {
  const active = field === current;
  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      className="flex items-center gap-1 hover:text-foreground"
    >
      {children}
      {active ? (
        order === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
      ) : (
        <ChevronsUpDown className="h-3 w-3 opacity-40" />
      )}
    </button>
  );
}

function RunRow({
  run,
  flowName,
  datasetName,
  projectById,
  fmt,
  onClick,
}: {
  run: FlowRunSummary;
  flowName: Map<string, string>;
  datasetName: Map<string, string>;
  projectById: Map<string, { name: string; color: string }>;
  fmt: (iso: string | null | undefined) => string;
  onClick: () => void;
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
        {run.project_id ? (
          (() => {
            const proj = projectById.get(run.project_id);
            const theme = projectColor(proj?.color);
            return (
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <span className={cn("h-2 w-2 rounded-full shrink-0", theme.dot)} />
                {proj?.name ?? "—"}
              </span>
            );
          })()
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2.5">
        <StatusBadge status={run.status} />
      </td>
      <td className="px-4 py-2.5 text-muted-foreground">
        {run.input_dataset_id ? datasetName.get(run.input_dataset_id) ?? "—" : "—"}
      </td>
      <td className="px-4 py-2.5 text-muted-foreground">{fmt(run.created_at)}</td>
      <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
        {formatDuration(run.started_at, run.finished_at)}
      </td>
    </tr>
  );
}

function RunCard({
  run,
  flowName,
  datasetName,
  projectById,
  fmt,
  onClick,
}: {
  run: FlowRunSummary;
  flowName: Map<string, string>;
  datasetName: Map<string, string>;
  projectById: Map<string, { name: string; color: string }>;
  fmt: (iso: string | null | undefined) => string;
  onClick: () => void;
}) {
  const proj = run.project_id ? projectById.get(run.project_id) : undefined;
  const theme = projectColor(proj?.color);
  return (
    <button
      onClick={onClick}
      className="animate-fade-in-up flex flex-col gap-2 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold leading-tight">
          {run.flow_name ?? flowName.get(run.flow_id) ?? "—"}
        </span>
        <StatusBadge status={run.status} />
      </div>
      {proj && (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className={cn("h-2 w-2 rounded-full shrink-0", theme.dot)} />
          {proj.name}
        </span>
      )}
      {run.input_dataset_id && (
        <span className="text-xs text-muted-foreground">
          {datasetName.get(run.input_dataset_id) ?? "—"}
        </span>
      )}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{fmt(run.created_at)}</span>
        <span className="tabular-nums">{formatDuration(run.started_at, run.finished_at)}</span>
      </div>
    </button>
  );
}
