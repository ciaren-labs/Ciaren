import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BadgeCheck, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { mlApi } from "@/lib/api";
import { formatMetric, metricLabel, splitMetrics } from "@/lib/mlMetrics";
import type { MlRegisterResult, NodeResult } from "@/lib/types";

/** Heat shade for a confusion-matrix cell, scaled to the matrix max. */
function heat(count: number, max: number): string {
  if (max === 0) return "rgba(168,85,247,0.05)";
  const a = 0.08 + (count / max) * 0.6;
  return `rgba(168,85,247,${a.toFixed(3)})`;
}

function ConfusionMatrixView({ matrix }: { matrix: number[][] }) {
  const max = Math.max(1, ...matrix.flat());
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Confusion matrix
      </span>
      <div className="inline-flex flex-col text-[11px]">
        {matrix.map((row, i) => (
          <div key={i} className="flex">
            {row.map((count, j) => (
              <div
                key={j}
                title={`true ${i} → predicted ${j}: ${count}`}
                className="flex h-8 w-8 items-center justify-center border border-background font-medium tabular-nums text-slate-700"
                style={{ backgroundColor: heat(count, max) }}
              >
                {count}
              </div>
            ))}
          </div>
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground">rows = true class · columns = predicted</span>
    </div>
  );
}

/** Horizontal bars for a featureImportance node's output sample. */
function FeatureImportanceChart({ sample }: { sample: Record<string, unknown>[] }) {
  const rows = sample
    .map((r) => ({ name: String(r.feature_name ?? ""), value: Number(r.importance ?? 0) }))
    .filter((r) => r.name);
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Feature importance
      </span>
      <div className="flex flex-col gap-1">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-2">
            <span className="w-24 shrink-0 truncate text-[11px] text-slate-600" title={r.name}>
              {r.name}
            </span>
            <div className="h-3 flex-1 overflow-hidden rounded-sm bg-muted">
              <div
                className="h-full rounded-sm bg-purple-400"
                style={{ width: `${(Math.abs(r.value) / max) * 100}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-[10px] tabular-nums text-muted-foreground">
              {formatMetric(r.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RegisterModelDialog({ runId }: { runId: string }) {
  const [name, setName] = useState("");
  const [stage, setStage] = useState("");
  const [result, setResult] = useState<MlRegisterResult | null>(null);

  const mutation = useMutation({
    mutationFn: () => mlApi.register(runId, { model_name: name.trim(), stage: stage || null }),
    onSuccess: setResult,
  });

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-purple-700"
        >
          <BadgeCheck className="h-3.5 w-3.5" /> Register in registry
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Register model</DialogTitle>
          <DialogDescription>
            Promote this run's model to the MLflow registry under a name, optionally tagging a stage.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Model name
            <Input value={name} placeholder="churn-predictor" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Stage (optional)
            <Select value={stage} onChange={(e) => setStage(e.target.value)}>
              <option value="">None</option>
              <option value="Staging">Staging</option>
              <option value="Production">Production</option>
              <option value="Archived">Archived</option>
            </Select>
          </label>
          {result && (
            <p className="rounded-md bg-success/10 px-2 py-1.5 text-xs text-success">
              Registered <strong>{result.model_name}</strong> v{result.version}
              {result.alias ? ` (alias: ${result.alias})` : ""}.
            </p>
          )}
          {mutation.isError && (
            <p className="rounded-md bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
              {(mutation.error as Error).message}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <button type="button" className="rounded-md border border-border px-3 py-1.5 text-xs">
                Close
              </button>
            </DialogClose>
            <button
              type="button"
              disabled={!name.trim() || mutation.isPending}
              onClick={() => mutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
            >
              {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Register
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** ML panel shown in the node inspector for ML nodes (metrics, model, charts). */
export function MlMetricsPanel({ result, runId }: { result: NodeResult; runId: string }) {
  const { scalars, confusion } = splitMetrics(result.ml_metrics);
  const hasContent =
    scalars.length > 0 ||
    confusion ||
    result.model_uri ||
    (result.cv_scores?.length ?? 0) > 0 ||
    result.type === "featureImportance";
  if (!hasContent) return null;

  return (
    <div className="flex flex-col gap-3 border-b border-border bg-purple-50/40 p-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-purple-700">
          Machine learning
        </span>
        {result.task_type && (
          <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-700">
            {result.task_type}
          </span>
        )}
      </div>

      {scalars.length > 0 && (
        <div className="grid grid-cols-2 gap-1.5">
          {scalars.map(([key, value]) => (
            <div key={key} className="rounded-md bg-card px-2 py-1.5 shadow-sm">
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {metricLabel(key)}
              </div>
              <div className="text-sm font-semibold tabular-nums text-slate-800">
                {formatMetric(value)}
              </div>
            </div>
          ))}
        </div>
      )}

      {result.cv_scores && result.cv_scores.length > 0 && (
        <div className="text-[11px] text-slate-600">
          <span className="font-medium">CV folds:</span>{" "}
          {result.cv_scores.map((s) => formatMetric(s)).join(", ")}
        </div>
      )}

      {confusion && <ConfusionMatrixView matrix={confusion.matrix} />}

      {result.type === "featureImportance" && <FeatureImportanceChart sample={result.sample} />}

      {result.model_uri && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Model URI</span>
            <code className="break-all rounded bg-muted px-1.5 py-1 text-[10px] text-slate-700">
              {result.model_uri}
            </code>
          </div>
          {result.mlflow_run_id && (
            <span className="text-[10px] text-muted-foreground">
              MLflow run {result.mlflow_run_id.slice(0, 12)}…
            </span>
          )}
          <RegisterModelDialog runId={runId} />
        </div>
      )}
    </div>
  );
}
