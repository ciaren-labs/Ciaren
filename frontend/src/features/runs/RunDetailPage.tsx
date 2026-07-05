import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { AlertCircle, ArrowLeft, Download, Loader2, RotateCcw, ShieldCheck, ShieldAlert, ShieldX, Square } from "lucide-react";
import { useCancelRun, useRetryRun, useRun } from "./hooks";
import { MlMetricsPanel } from "./MlMetricsPanel";
import { useFlow } from "@/features/flows/hooks";
import { useDatasets } from "@/features/datasets/hooks";
import { RunDag } from "@/components/run/RunDag";
import { DataTable } from "@/components/flow/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDuration } from "@/lib/format";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { getNodeIcon } from "@/lib/nodeVisuals";
import { cn } from "@/lib/utils";
import type { InputDatasetRef, NodeResult, ParameterValues } from "@/lib/types";

const OUTPUT_NODE_TYPES = new Set(["fileOutput", "csvOutput", "excelOutput", "parquetOutput"]);

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = useRun(runId ?? null);
  const { data: flow } = useFlow(run?.flow_id ?? null);
  const { data: datasets } = useDatasets();
  const retry = useRetryRun();
  const cancel = useCancelRun();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const handleRetry = () => {
    if (!run) return;
    if (!confirm("Re-run this flow with the same config? This creates a new run (a new run id) — the current one is kept.")) return;
    retry.mutate(run.id, { onSuccess: (created) => navigate(`/runs/${created.id}`) });
  };

  const fmt = useFormatDateTime();
  const results = useMemo(() => run?.node_results ?? [], [run]);
  const selected = results.find((r) => r.node_id === selectedNodeId) ?? null;

  // On a failed run, auto-select the node that failed so its error is shown in
  // the inspector immediately — no hunting for the red node on the canvas.
  useEffect(() => {
    if (selectedNodeId !== null) return;
    const failed = results.find((r) => r.status === "failed");
    if (failed) setSelectedNodeId(failed.node_id);
  }, [results, selectedNodeId]);

  const datasetName = useMemo(
    () => new Map((datasets ?? []).map((d) => [d.id, d.name])),
    [datasets],
  );
  // Prefer the structured per-input list; fall back to the single primary id
  // for runs recorded before multi-input tracking existed.
  const inputs: InputDatasetRef[] = useMemo(() => {
    if (run?.input_datasets?.length) return run.input_datasets;
    if (run?.input_dataset_id) {
      return [{ dataset_id: run.input_dataset_id, version_number: null }];
    }
    return [];
  }, [run]);

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
          {run.status === "running" && (
            <button
              onClick={() => cancel.mutate(run.id)}
              disabled={cancel.isPending}
              title="Stop this run (finishes the current node, then stops)"
              className="flex items-center gap-1.5 rounded-md border border-destructive/40 px-2.5 py-1.5 font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
            >
              <Square className="h-3.5 w-3.5" />
              {cancel.isPending ? "Stopping…" : "Stop"}
            </button>
          )}
          {run.status === "failed" && (
            <button
              onClick={handleRetry}
              disabled={retry.isPending}
              title="Re-run the flow with the same config (creates a new run)"
              className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
            >
              <RotateCcw className={cn("h-3.5 w-3.5", retry.isPending && "animate-spin")} />
              {retry.isPending ? "Retrying…" : "Retry"}
            </button>
          )}
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
            <RunSummary
              results={results}
              inputs={inputs}
              datasetName={datasetName}
              parameters={run.parameters}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

function RunSummary({
  results,
  inputs,
  datasetName,
  parameters,
}: {
  results: NodeResult[];
  inputs: InputDatasetRef[];
  datasetName: Map<string, string>;
  parameters: ParameterValues | null;
}) {
  const paramEntries = Object.entries(parameters ?? {});
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
      {inputs.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {inputs.length > 1 ? "Input datasets" : "Input dataset"}
          </span>
          <div className="flex flex-wrap gap-1.5">
            {inputs.map((d) => (
              <span
                key={`${d.dataset_id}:${d.version_number}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-0.5 text-xs font-medium text-slate-600 shadow-sm"
              >
                {datasetName.get(d.dataset_id) ?? "Unknown dataset"}
                {d.version_number != null && (
                  <span className="text-muted-foreground">v{d.version_number}</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
      {paramEntries.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Parameters
          </span>
          <div className="flex flex-wrap gap-1.5">
            {paramEntries.map(([name, value]) => (
              <span
                key={name}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-0.5 text-xs shadow-sm"
              >
                <code className="font-medium">{name}</code>
                <span className="text-muted-foreground">{JSON.stringify(value)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
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

function AssertionBadgePanel({ result }: { result: NodeResult }) {
  const passed = result.assertion_passed;
  const count = result.assertion_violation_count;
  const sample = result.assertion_violating_sample ?? [];

  if (passed == null) return null;

  const Icon = passed ? ShieldCheck : result.status === "failed" ? ShieldX : ShieldAlert;
  const tone = passed
    ? "text-emerald-600 bg-emerald-50 border-emerald-200"
    : result.status === "failed"
      ? "text-red-600 bg-red-50 border-red-200"
      : "text-amber-600 bg-amber-50 border-amber-200";

  return (
    <div className="border-b border-border px-4 py-3">
      <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${tone}`}>
        <Icon className="h-4 w-4 shrink-0" />
        <div className="flex-1 text-xs font-medium">
          {passed ? (
            "All rows passed the assertion"
          ) : (
            <>
              {count} row{count !== 1 ? "s" : ""} violated the assertion
              {result.status === "failed" ? " (run stopped)" : " (continued with warning)"}
            </>
          )}
        </div>
      </div>
      {!passed && sample.length > 0 && (
        <div className="mt-2">
          <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Violating rows (up to 5)
          </div>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {Object.keys(sample[0]).map((col) => (
                    <th key={col} className="px-2.5 py-1.5 text-left font-medium text-muted-foreground">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sample.map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="px-2.5 py-1.5 font-mono text-slate-700">
                        {val == null ? <span className="text-muted-foreground">null</span> : String(val)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
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

      {result.status === "success" && <MlMetricsPanel result={result} runId={runId} />}

      {result.assertion_passed != null && (
        <AssertionBadgePanel result={result} />
      )}

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
