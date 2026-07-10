import { useMemo, useState } from "react";
import { Trophy } from "lucide-react";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type { MlExperimentRun } from "@/features/models/types";
import { useExperimentRuns, useMlExperiments } from "../hooks";
import { fmtMetric, HEADLINE_PRIORITY, LOWER_IS_BETTER } from "./mlFormat";
import { EmptyBox, ErrorBox, Loading, LineageChips } from "./shared";

export function ExperimentsTab({ flowName }: { flowName: Map<string, string> }) {
  const { data: experiments, isLoading, isError } = useMlExperiments();
  const [selected, setSelected] = useState<string | null>(null);
  const fmt = useFormatDateTime();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorBox what="experiments" />;
  if (!experiments || experiments.length === 0) {
    return (
      <EmptyBox
        title="No experiments yet"
        body="Run a flow with a Train Model node — each training run is logged to an MLflow experiment."
      />
    );
  }

  const activeId = selected ?? experiments[0].experiment_id;

  return (
    <div className="mt-4 grid grid-cols-[210px_1fr] gap-4">
      <div className="flex flex-col gap-1">
        {experiments.map((e) => (
          <button
            key={e.experiment_id}
            onClick={() => setSelected(e.experiment_id)}
            className={cn(
              "rounded-md px-3 py-2 text-left transition-colors",
              e.experiment_id === activeId ? "bg-accent" : "hover:bg-muted",
            )}
          >
            <div className="truncate text-sm font-medium">{e.name}</div>
            <div className="text-[11px] text-muted-foreground">
              {e.last_run ? `last run ${fmt(e.last_run)}` : "no runs yet"}
            </div>
          </button>
        ))}
      </div>
      <ExperimentDetail key={activeId} experimentId={activeId} flowName={flowName} />
    </div>
  );
}

function ExperimentDetail({ experimentId, flowName }: { experimentId: string; flowName: Map<string, string> }) {
  const { data: runs, isLoading, isError } = useExperimentRuns(experimentId);
  const fmt = useFormatDateTime();
  const [primary, setPrimary] = useState<string | null>(null);

  const metricKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const r of runs ?? []) for (const k of Object.keys(r.metrics)) keys.add(k);
    return [...keys];
  }, [runs]);

  // Default primary metric: first headline-priority metric present, else first.
  const primaryMetric = useMemo(() => {
    if (primary && metricKeys.includes(primary)) return primary;
    return HEADLINE_PRIORITY.find((k) => metricKeys.includes(k)) ?? metricKeys[0] ?? null;
  }, [primary, metricKeys]);

  const better = (k: string) => (LOWER_IS_BETTER.test(k) ? Math.min : Math.max);

  // Best value per metric column (for the highlight + bar scale).
  const best = useMemo(() => {
    const out: Record<string, number> = {};
    for (const k of metricKeys) {
      const vals = (runs ?? []).map((r) => r.metrics[k]).filter((v): v is number => v != null);
      if (vals.length) out[k] = better(k)(...vals);
    }
    return out;
  }, [runs, metricKeys]);

  // Sort rows by the primary metric (respecting direction).
  const sortedRuns = useMemo(() => {
    if (!runs) return [];
    if (!primaryMetric) return runs;
    const dir = LOWER_IS_BETTER.test(primaryMetric) ? 1 : -1;
    return [...runs].sort((a, b) => {
      const av = a.metrics[primaryMetric];
      const bv = b.metrics[primaryMetric];
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av - bv) * dir;
    });
  }, [runs, primaryMetric]);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorBox what="runs" />;
  if (!runs || runs.length === 0) {
    return <EmptyBox title="No runs in this experiment" body="" />;
  }

  const bestRun = sortedRuns[0];
  const bestHead = primaryMetric && bestRun.metrics[primaryMetric] != null
    ? { key: primaryMetric, value: bestRun.metrics[primaryMetric] }
    : null;

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {/* Summary header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs text-muted-foreground">Runs</div>
            <div className="text-xl font-bold tabular-nums">{runs.length}</div>
          </div>
          {bestHead && (
            <div className="border-l border-border pl-4">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Trophy className="h-3 w-3 text-amber-500" /> Best {bestHead.key}
              </div>
              <div className="text-xl font-bold tabular-nums text-emerald-600">{fmtMetric(bestHead.value)}</div>
              <div className="text-[11px] text-muted-foreground">
                {bestRun.params.model_type ?? bestRun.run_name}
                {bestRun.lineage.flow_id && (
                  <> · from <span className="font-medium text-foreground">{flowName.get(bestRun.lineage.flow_id) ?? "a flow"}</span></>
                )}
              </div>
            </div>
          )}
        </div>
        {metricKeys.length > 0 && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Rank by
            <select
              value={primaryMetric ?? ""}
              onChange={(e) => setPrimary(e.target.value)}
              className="rounded-md border border-input bg-background px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {metricKeys.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {/* Leaderboard */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2 font-semibold">#</th>
              <th className="px-3 py-2 font-semibold">Run</th>
              <th className="px-3 py-2 font-semibold">Model</th>
              <th className="px-3 py-2 font-semibold">When</th>
              {metricKeys.map((k) => (
                <th key={k} className="px-3 py-2 font-semibold">
                  <button
                    onClick={() => setPrimary(k)}
                    className={cn(
                      "[letter-spacing:inherit] [text-transform:inherit] hover:text-foreground",
                      k === primaryMetric && "text-foreground underline",
                    )}
                  >
                    {k}
                  </button>
                </th>
              ))}
              <th className="px-3 py-2 font-semibold">Flow &amp; run</th>
            </tr>
          </thead>
          <tbody>
            {sortedRuns.map((r, i) => (
              <RunRow
                key={r.run_id}
                rank={i + 1}
                run={r}
                metricKeys={metricKeys}
                best={best}
                primaryMetric={primaryMetric}
                when={fmt(r.start_time)}
                flowName={flowName}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunRow({
  rank,
  run,
  metricKeys,
  best,
  primaryMetric,
  when,
  flowName,
}: {
  rank: number;
  run: MlExperimentRun;
  metricKeys: string[];
  best: Record<string, number>;
  primaryMetric: string | null;
  when: string;
  flowName: Map<string, string>;
}) {
  return (
    <tr className="border-b border-border/50">
      <td className="px-3 py-2 tabular-nums text-muted-foreground">
        {rank === 1 ? <Trophy className="h-3.5 w-3.5 text-amber-500" /> : rank}
      </td>
      <td className="px-3 py-2 font-mono text-xs">{run.run_name}</td>
      <td className="px-3 py-2">{run.params.model_type ?? "—"}</td>
      <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">{when}</td>
      {metricKeys.map((k) => {
        const v = run.metrics[k];
        if (v == null) return <td key={k} className="px-3 py-2 text-muted-foreground">—</td>;
        const isBest = best[k] === v;
        // Bar width relative to the best in the column (only meaningful for >=0).
        const ratio = best[k] ? Math.max(0, Math.min(1, v / best[k])) : 0;
        const width = LOWER_IS_BETTER.test(k)
          ? (v ? Math.max(0, Math.min(1, best[k] / v)) : 0) * 100
          : ratio * 100;
        return (
          <td key={k} className="px-3 py-2">
            <div className="flex flex-col gap-0.5">
              <span className={cn("tabular-nums", isBest && "font-semibold text-emerald-600", k === primaryMetric && "font-semibold")}>
                {fmtMetric(v)}
              </span>
              <span className="h-1 w-16 overflow-hidden rounded-full bg-muted">
                <span
                  className={cn("block h-full rounded-full", isBest ? "bg-emerald-500" : "bg-brand-300")}
                  style={{ width: `${Number.isFinite(width) ? width : 0}%` }}
                />
              </span>
            </div>
          </td>
        );
      })}
      <td className="px-3 py-2"><LineageChips lineage={run.lineage} flowName={flowName} /></td>
    </tr>
  );
}
