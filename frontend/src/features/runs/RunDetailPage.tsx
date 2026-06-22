import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { AlertCircle, ArrowLeft, Download, Loader2 } from "lucide-react";
import { useRun } from "./hooks";
import { useFlow } from "@/features/flows/hooks";
import { RunDag } from "@/components/run/RunDag";
import { DataTable } from "@/components/flow/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDuration } from "@/lib/format";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { getNodeIcon } from "@/lib/nodeVisuals";
import type { NodeResult } from "@/lib/types";

const OUTPUT_NODE_TYPES = new Set(["csvOutput", "excelOutput", "parquetOutput"]);

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = useRun(runId ?? null);
  const { data: flow } = useFlow(run?.flow_id ?? null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const fmt = useFormatDateTime();
  const results = useMemo(() => run?.node_results ?? [], [run]);
  const selected = results.find((r) => r.node_id === selectedNodeId) ?? null;

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading run…
      </div>
    );
  }
  if (!run) {
    return <div className="p-6 text-sm text-destructive">Run not found.</div>;
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background/80 px-4 py-2 backdrop-blur">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/runs")}
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Runs
          </button>
          <h1 className="text-sm font-semibold">{flow?.name ?? "Flow run"}</h1>
          <StatusBadge status={run.status} />
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>Started {fmt(run.created_at)}</span>
          <span>Duration {formatDuration(run.started_at, run.finished_at)}</span>
        </div>
      </div>

      {run.status === "failed" && run.error_message && (
        <div className="flex items-start gap-2 border-b border-destructive/20 bg-destructive/5 px-4 py-2 text-xs text-destructive">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="font-mono">{run.error_message}</span>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* Read-only DAG */}
        <div className="min-w-0 flex-1">
          {flow?.graph_json ? (
            <ReactFlowProvider>
              <RunDag
                graph={flow.graph_json}
                results={results}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
              />
            </ReactFlowProvider>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              The flow graph is no longer available.
            </div>
          )}
        </div>

        {/* Node inspector */}
        <aside className="flex w-[26rem] shrink-0 flex-col border-l border-border bg-muted/20">
          {selected ? (
            <NodeInspector result={selected} runId={runId ?? ""} />
          ) : (
            <RunSummary results={results} />
          )}
        </aside>
      </div>
    </div>
  );
}

function RunSummary({ results }: { results: NodeResult[] }) {
  const counts = results.reduce(
    (acc, r) => ({ ...acc, [r.status]: (acc[r.status] ?? 0) + 1 }),
    {} as Record<string, number>,
  );
  return (
    <div className="flex flex-col gap-3 p-4">
      <h2 className="text-sm font-semibold">Run summary</h2>
      <p className="text-xs text-muted-foreground">
        Select a node in the graph to inspect its output rows and columns.
      </p>
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Succeeded" value={counts.success ?? 0} tone="text-success" />
        <Stat label="Failed" value={counts.failed ?? 0} tone="text-destructive" />
        <Stat label="Skipped" value={counts.skipped ?? 0} tone="text-muted-foreground" />
      </div>
      <div className="mt-1 flex flex-col gap-1">
        {results.map((r) => (
          <div
            key={r.node_id}
            className="flex items-center justify-between rounded-md bg-card px-2.5 py-1.5 text-xs shadow-sm"
          >
            <span className="truncate font-medium">{r.label}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2.5 text-center shadow-sm">
      <div className={`text-lg font-semibold ${tone}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}

function NodeInspector({ result, runId }: { result: NodeResult; runId: string }) {
  const Icon = getNodeIcon(result.type);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2.5 border-b border-border p-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{result.label}</div>
          <div className="text-[11px] text-muted-foreground">
            {result.rows !== null ? `${result.rows} rows · ` : ""}
            {result.columns.length} columns
          </div>
        </div>
        <StatusBadge status={result.status} />
      </div>

      {OUTPUT_NODE_TYPES.has(result.type) && result.status === "success" && (
        <div className="border-b border-border px-4 py-2">
          <a
            href={`/api/runs/${runId}/output?node_id=${encodeURIComponent(result.node_id)}`}
            download
            className="inline-flex items-center gap-1.5 rounded-md bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700 transition-colors hover:bg-brand-100"
          >
            <Download className="h-4 w-4" /> Download output
          </a>
        </div>
      )}

      {result.status === "failed" && result.error ? (
        <div className="m-4 rounded-lg bg-destructive/5 p-3 text-xs text-destructive">
          <p className="mb-1 font-semibold">This node failed:</p>
          <p className="font-mono">{result.error}</p>
        </div>
      ) : result.status === "skipped" ? (
        <p className="p-4 text-sm text-muted-foreground">
          This node was skipped because an upstream node failed.
        </p>
      ) : result.sample.length > 0 ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="px-4 pt-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Output preview (first {result.sample.length} rows)
          </div>
          <div className="p-2">
            <DataTable columns={result.columns} rows={result.sample} />
          </div>
        </div>
      ) : (
        <p className="p-4 text-sm text-muted-foreground">No preview rows recorded.</p>
      )}
    </div>
  );
}
