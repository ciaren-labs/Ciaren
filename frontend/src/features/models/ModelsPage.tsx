import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BrainCircuit, FlaskConical, GitBranch, Loader2, Tag } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type {
  MlExperimentRun,
  MlLineage,
  MlRegisteredModel,
} from "@/lib/types";
import {
  useExperimentRuns,
  useMlEnabled,
  useMlExperiments,
  useRegisteredModels,
} from "./hooks";

// Lower-is-better metric names (everything else is treated as higher-is-better)
// so the leaderboard can highlight the best value per column.
const LOWER_IS_BETTER = /rmse|mae|mse|error|loss|inertia/i;

function fmtMetric(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(4);
}

export function ModelsPage() {
  const mlEnabled = useMlEnabled();

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <BrainCircuit className="h-6 w-6 text-purple-600" /> ML Models
        </h1>
        <p className="text-sm text-muted-foreground">
          Models and experiments tracked with MLflow — with links back to the
          flows and runs that produced them.
        </p>
      </div>

      {!mlEnabled ? (
        <MlDisabledNotice />
      ) : (
        <Tabs defaultValue="models">
          <TabsList>
            <TabsTrigger value="models">
              <Tag className="mr-1.5 h-4 w-4" /> Registered Models
            </TabsTrigger>
            <TabsTrigger value="experiments">
              <FlaskConical className="mr-1.5 h-4 w-4" /> Experiments
            </TabsTrigger>
          </TabsList>
          <TabsContent value="models">
            <RegisteredModelsTab />
          </TabsContent>
          <TabsContent value="experiments">
            <ExperimentsTab />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function MlDisabledNotice() {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <BrainCircuit className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
      <p className="text-sm font-medium">The ML extension isn’t enabled</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Install it with <code className="font-mono">pip install &quot;flowframe[ml]&quot;</code> and set{" "}
        <code className="font-mono">FLOWFRAME_ML_ENABLED=true</code> to train and track models.
      </p>
    </div>
  );
}

// ─── Registered models ──────────────────────────────────────────────────────

function RegisteredModelsTab() {
  const { data: models, isLoading, isError } = useRegisteredModels();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorBox what="registered models" />;
  if (!models || models.length === 0) {
    return (
      <EmptyBox
        title="No registered models yet"
        body="Open a successful run with a Train Model node and click “Register in registry” to promote it here."
      />
    );
  }

  return (
    <div className="mt-4 flex flex-col gap-4">
      {models.map((m) => (
        <ModelCard key={m.name} model={m} />
      ))}
    </div>
  );
}

function ModelCard({ model }: { model: MlRegisteredModel }) {
  const fmt = useFormatDateTime();
  // Metric columns shown for the versions: the union across versions, capped.
  const metricKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const v of model.versions) for (const k of Object.keys(v.metrics)) keys.add(k);
    return [...keys].slice(0, 5);
  }, [model.versions]);

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{model.name}</span>
        {Object.entries(model.aliases).map(([alias, version]) => (
          <span
            key={alias}
            className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700"
            title={`@${alias} → version ${version}`}
          >
            @{alias} → v{version}
          </span>
        ))}
        {model.last_updated && (
          <span className="ml-auto text-xs text-muted-foreground">
            updated {fmt(model.last_updated)}
          </span>
        )}
      </div>
      {model.description && (
        <p className="mt-1 text-sm text-muted-foreground">{model.description}</p>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="py-1.5 pr-3 font-medium">Version</th>
              <th className="py-1.5 pr-3 font-medium">Aliases</th>
              {metricKeys.map((k) => (
                <th key={k} className="py-1.5 pr-3 font-medium">{k}</th>
              ))}
              <th className="py-1.5 pr-3 font-medium">Lineage</th>
            </tr>
          </thead>
          <tbody>
            {model.versions.map((v) => (
              <tr key={v.version} className="border-b border-border/50">
                <td className="py-1.5 pr-3 font-medium">v{v.version}</td>
                <td className="py-1.5 pr-3">
                  {v.aliases.length ? v.aliases.join(", ") : <span className="text-muted-foreground">—</span>}
                </td>
                {metricKeys.map((k) => (
                  <td key={k} className="py-1.5 pr-3 tabular-nums">
                    {k in v.metrics ? fmtMetric(v.metrics[k]) : <span className="text-muted-foreground">—</span>}
                  </td>
                ))}
                <td className="py-1.5 pr-3">
                  <LineageLinks lineage={v.lineage} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LineageLinks({ lineage }: { lineage: MlLineage }) {
  if (!lineage.flow_id && !lineage.run_id) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className="flex items-center gap-2 text-xs">
      <GitBranch className="h-3 w-3 text-muted-foreground" />
      {lineage.flow_id && (
        <Link to={`/flows/${lineage.flow_id}`} className="text-primary hover:underline">
          flow
        </Link>
      )}
      {lineage.run_id && (
        <Link to={`/runs/${lineage.run_id}`} className="text-primary hover:underline">
          run
        </Link>
      )}
      {lineage.dataset_ids?.length ? (
        <span className="text-muted-foreground">
          · {lineage.dataset_ids.length} dataset{lineage.dataset_ids.length > 1 ? "s" : ""}
        </span>
      ) : null}
    </span>
  );
}

// ─── Experiments leaderboard ────────────────────────────────────────────────

function ExperimentsTab() {
  const { data: experiments, isLoading, isError } = useMlExperiments();
  const [selected, setSelected] = useState<string | null>(null);

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
    <div className="mt-4 grid grid-cols-[200px_1fr] gap-4">
      <div className="flex flex-col gap-1">
        {experiments.map((e) => (
          <button
            key={e.experiment_id}
            onClick={() => setSelected(e.experiment_id)}
            className={cn(
              "rounded-md px-3 py-2 text-left text-sm transition-colors",
              e.experiment_id === activeId
                ? "bg-accent font-medium text-accent-foreground"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            <div className="truncate">{e.name}</div>
          </button>
        ))}
      </div>
      <Leaderboard experimentId={activeId} />
    </div>
  );
}

function Leaderboard({ experimentId }: { experimentId: string }) {
  const { data: runs, isLoading, isError } = useExperimentRuns(experimentId);
  const fmt = useFormatDateTime();

  const metricKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const r of runs ?? []) for (const k of Object.keys(r.metrics)) keys.add(k);
    return [...keys];
  }, [runs]);

  // Best value per metric column (for highlighting), respecting lower-is-better.
  const best = useMemo(() => {
    const out: Record<string, number> = {};
    for (const k of metricKeys) {
      const vals = (runs ?? []).map((r) => r.metrics[k]).filter((v): v is number => v != null);
      if (!vals.length) continue;
      out[k] = LOWER_IS_BETTER.test(k) ? Math.min(...vals) : Math.max(...vals);
    }
    return out;
  }, [runs, metricKeys]);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorBox what="runs" />;
  if (!runs || runs.length === 0) {
    return <EmptyBox title="No runs in this experiment" body="" />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Run</th>
            <th className="px-3 py-2 font-medium">Model</th>
            <th className="px-3 py-2 font-medium">When</th>
            {metricKeys.map((k) => (
              <th key={k} className="px-3 py-2 font-medium">{k}</th>
            ))}
            <th className="px-3 py-2 font-medium">Lineage</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <RunRow key={r.run_id} run={r} metricKeys={metricKeys} best={best} when={fmt(r.start_time)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunRow({
  run,
  metricKeys,
  best,
  when,
}: {
  run: MlExperimentRun;
  metricKeys: string[];
  best: Record<string, number>;
  when: string;
}) {
  return (
    <tr className="border-b border-border/50">
      <td className="px-3 py-2 font-mono text-xs">{run.run_name}</td>
      <td className="px-3 py-2">{run.params.model_type ?? "—"}</td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{when}</td>
      {metricKeys.map((k) => {
        const v = run.metrics[k];
        const isBest = v != null && best[k] === v;
        return (
          <td
            key={k}
            className={cn("px-3 py-2 tabular-nums", isBest && "font-semibold text-emerald-600")}
          >
            {v != null ? fmtMetric(v) : <span className="text-muted-foreground">—</span>}
          </td>
        );
      })}
      <td className="px-3 py-2">
        <LineageLinks lineage={run.lineage} />
      </td>
    </tr>
  );
}

// ─── Shared bits ────────────────────────────────────────────────────────────

function Loading() {
  return (
    <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </p>
  );
}

function ErrorBox({ what }: { what: string }) {
  return (
    <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
      Could not load {what}. Check that the MLflow tracking store is reachable (Connections → Local MLflow).
    </div>
  );
}

function EmptyBox({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-4 rounded-lg border border-dashed border-border p-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{body}</p>}
    </div>
  );
}
