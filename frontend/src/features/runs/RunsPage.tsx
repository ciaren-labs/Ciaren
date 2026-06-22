import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { History, Loader2, RotateCcw } from "lucide-react";
import { useRuns } from "./hooks";
import { useFlows } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTime, formatDuration } from "@/lib/format";
import type { RunListFilters, RunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const STATUSES: RunStatus[] = ["success", "failed", "running", "pending"];

export function RunsPage() {
  const navigate = useNavigate();
  const { data: flows } = useFlows();
  const { data: datasets } = useDatasets();

  const [flowId, setFlowId] = useState("");
  const [status, setStatus] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");

  const filters: RunListFilters = useMemo(
    () => ({
      flow_id: flowId || undefined,
      status: (status || undefined) as RunStatus | undefined,
      dataset_id: datasetId || undefined,
      started_after: after ? `${after}T00:00:00` : undefined,
      started_before: before ? `${before}T23:59:59` : undefined,
    }),
    [flowId, status, datasetId, after, before],
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

  const hasFilters = flowId || status || datasetId || after || before;
  const reset = () => {
    setFlowId("");
    setStatus("");
    setDatasetId("");
    setAfter("");
    setBefore("");
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-5 flex items-center gap-2.5">
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

      {/* Filter bar */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-3 shadow-sm">
        <Filter label="Flow">
          <select className={SELECT_CLASS} value={flowId} onChange={(e) => setFlowId(e.target.value)}>
            <option value="">All flows</option>
            {(flows ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </Filter>
        <Filter label="Status">
          <select className={SELECT_CLASS} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s[0].toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </Filter>
        <Filter label="Dataset">
          <select
            className={SELECT_CLASS}
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
          >
            <option value="">All datasets</option>
            {(datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Filter>
        <Filter label="From">
          <input
            type="date"
            className={SELECT_CLASS}
            value={after}
            onChange={(e) => setAfter(e.target.value)}
          />
        </Filter>
        <Filter label="To">
          <input
            type="date"
            className={SELECT_CLASS}
            value={before}
            onChange={(e) => setBefore(e.target.value)}
          />
        </Filter>
        {hasFilters && (
          <button
            onClick={reset}
            className="flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Clear
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading runs…
        </p>
      ) : runs && runs.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-semibold">Flow</th>
                <th className="px-4 py-2.5 text-left font-semibold">Status</th>
                <th className="px-4 py-2.5 text-left font-semibold">Dataset</th>
                <th className="px-4 py-2.5 text-left font-semibold">Started</th>
                <th className="px-4 py-2.5 text-left font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  onClick={() => navigate(`/runs/${run.id}`)}
                  className={cn(
                    "cursor-pointer border-t border-border transition-colors hover:bg-accent/40",
                  )}
                >
                  <td className="px-4 py-2.5 font-medium">
                    {run.flow_name ?? flowName.get(run.flow_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {run.input_dataset_id
                      ? datasetName.get(run.input_dataset_id) ?? "—"
                      : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {formatDateTime(run.created_at)}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
