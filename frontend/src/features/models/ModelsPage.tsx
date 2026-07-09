import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BrainCircuit,
  Check,
  Copy,
  FlaskConical,
  GitBranch,
  Loader2,
  Plus,
  Tag,
  Trophy,
  X,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useFlows } from "@/features/flows/hooks";
import { useProjects } from "@/features/projects/hooks";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type {
  MlExperimentRun,
  MlLineage,
  MlModelVersion,
  MlRegisteredModel,
} from "@/lib/types";
import {
  useClearModelAlias,
  useExperimentRuns,
  useMlEnabled,
  useMlExperiments,
  useRegisteredModels,
  useSetModelAlias,
} from "./hooks";

// Lower-is-better metric names (everything else is higher-is-better) so the
// leaderboard bars/highlights and "best" picks point the right way.
const LOWER_IS_BETTER = /rmse|mae|mse|error|loss|inertia/i;
// Preference order for the single "headline" metric shown on summary cards.
const HEADLINE_PRIORITY = [
  "train_f1_weighted",
  "train_accuracy",
  "train_r2",
  "explained_variance",
  "silhouette",
  "cv_mean",
];

function fmtMetric(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(4);
}

function headlineMetric(metrics: Record<string, number>): { key: string; value: number } | null {
  const keys = Object.keys(metrics);
  if (keys.length === 0) return null;
  const key = HEADLINE_PRIORITY.find((k) => k in metrics) ?? keys[0];
  return { key, value: metrics[key] };
}

export function ModelsPage() {
  const mlEnabled = useMlEnabled();
  const { data: flows } = useFlows();
  const { data: projects } = useProjects();
  const flowName = useMemo(() => new Map((flows ?? []).map((f) => [f.id, f.name])), [flows]);
  const flowProject = useMemo(
    () => new Map((flows ?? []).map((f) => [f.id, f.project_id])),
    [flows],
  );
  const projectName = useMemo(() => new Map((projects ?? []).map((p) => [p.id, p.name])), [projects]);
  const projectColorById = useMemo(
    () => new Map((projects ?? []).map((p) => [p.id, p.color])),
    [projects],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
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
            <RegisteredModelsTab
              flowName={flowName}
              flowProject={flowProject}
              projectName={projectName}
              projectColorById={projectColorById}
            />
          </TabsContent>
          <TabsContent value="experiments">
            <ExperimentsTab flowName={flowName} />
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
      <p className="text-sm font-medium">Machine learning is disabled</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Set <code className="font-mono">CIAREN_ML_ENABLED=true</code> to train and track models.
        If it's already set, run <code className="font-mono">ciaren check</code> — this usually
        means scikit-learn, MLflow, or joblib failed to import.
      </p>
    </div>
  );
}

// ─── Shared bits ────────────────────────────────────────────────────────────

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      }}
      title={`Copy ${label}`}
      className="inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
      {label}
    </button>
  );
}

function LineageChips({
  lineage,
  flowName,
}: {
  lineage: MlLineage;
  flowName?: Map<string, string>;
}) {
  if (!lineage.flow_id && !lineage.run_id) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const label = lineage.flow_id ? flowName?.get(lineage.flow_id) ?? "Flow" : null;
  return (
    <span className="flex items-center gap-1.5 whitespace-nowrap">
      {lineage.flow_id && (
        <Link
          to={`/flows/${lineage.flow_id}`}
          title={label ?? undefined}
          className="inline-flex max-w-[160px] items-center gap-1 truncate rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 transition-colors hover:bg-brand-100"
        >
          <GitBranch className="h-3 w-3 shrink-0" /> <span className="truncate">{label}</span>
        </Link>
      )}
      {lineage.run_id && (
        <Link
          to={`/runs/${lineage.run_id}`}
          className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent"
        >
          Run
        </Link>
      )}
    </span>
  );
}

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

// ─── Registered models ──────────────────────────────────────────────────────

const NO_PROJECT = "__none__";

function RegisteredModelsTab({
  flowName,
  flowProject,
  projectName,
  projectColorById,
}: {
  flowName: Map<string, string>;
  flowProject: Map<string, string | null>;
  projectName: Map<string, string>;
  projectColorById: Map<string, string | null | undefined>;
}) {
  const { data: models, isLoading, isError } = useRegisteredModels();
  const [projectFilter, setProjectFilter] = useState("");

  // A model's project = the project of the flow that produced its production (or
  // latest) version. Multi-project models fall under their representative version.
  const projectOf = (m: MlRegisteredModel): string => {
    const v = m.versions.find((x) => x.version === m.aliases.production) ?? m.versions[0];
    const flowId = v?.lineage.flow_id;
    return (flowId && flowProject.get(flowId)) || NO_PROJECT;
  };

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

  // Group models by project for the segmented view.
  const groups = new Map<string, MlRegisteredModel[]>();
  for (const m of models) {
    const pid = projectOf(m);
    if (projectFilter && pid !== projectFilter) continue;
    (groups.get(pid) ?? groups.set(pid, []).get(pid)!).push(m);
  }
  const projectLabel = (pid: string) =>
    pid === NO_PROJECT ? "No project" : projectName.get(pid) ?? "Unknown project";

  // Filter options: only projects that actually own a registered model.
  const presentProjects = [...new Set(models.map(projectOf))];

  return (
    <div className="mt-4 flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Project</span>
        <div className="w-56">
          <SearchableSelect
            value={projectFilter}
            onChange={setProjectFilter}
            allLabel="All projects"
            placeholder="Filter by project…"
            options={presentProjects.map((pid) => ({ value: pid, label: projectLabel(pid) }))}
          />
        </div>
      </div>

      {[...groups.entries()].map(([pid, group]) => (
        <CollapsibleSection
          key={pid}
          title={projectLabel(pid)}
          colorKey={projectColorById.get(pid)}
          showDot={pid !== NO_PROJECT}
          count={group.length}
        >
          <div className="flex flex-col gap-3">
            <SummaryStrip models={group} flowName={flowName} />
            <div className="flex flex-col gap-4">
              {group.map((m) => (
                <ModelCard key={m.name} model={m} flowName={flowName} />
              ))}
            </div>
          </div>
        </CollapsibleSection>
      ))}
    </div>
  );
}

/** "At a glance" cards: each registered model's production (or latest) version and
 * its headline metric — the quick "what's my best model" answer. */
function SummaryStrip({ models, flowName }: { models: MlRegisteredModel[]; flowName: Map<string, string> }) {
  const cards = models.map((m) => {
    const prodVersion = m.aliases.production;
    const chosen =
      m.versions.find((v) => v.version === prodVersion) ?? m.versions[0];
    return { model: m, version: chosen, isProd: !!prodVersion && chosen?.version === prodVersion };
  });

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map(({ model, version, isProd }) => {
        const head = version ? headlineMetric(version.metrics) : null;
        return (
          <div key={model.name} className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              <span className="truncate font-semibold">{model.name}</span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              {head ? (
                <>
                  <span className="text-2xl font-bold tabular-nums">{fmtMetric(head.value)}</span>
                  <span className="text-xs text-muted-foreground">{head.key}</span>
                </>
              ) : (
                <span className="text-sm text-muted-foreground">no metrics</span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span className={cn("rounded px-1.5 py-0.5 font-medium", isProd ? "bg-purple-100 text-purple-700" : "bg-muted")}>
                {isProd ? "@production" : "latest"} · v{version?.version ?? "—"}
              </span>
              {version && <LineageChips lineage={version.lineage} flowName={flowName} />}
            </div>
            {version?.lineage.flow_id && (
              <div className="mt-1 text-[11px] text-muted-foreground">
                winner from{" "}
                <span className="font-medium text-foreground">
                  {flowName.get(version.lineage.flow_id) ?? "a flow"}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ModelCard({ model, flowName }: { model: MlRegisteredModel; flowName: Map<string, string> }) {
  const fmt = useFormatDateTime();
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
          <span className="ml-auto text-xs text-muted-foreground">updated {fmt(model.last_updated)}</span>
        )}
      </div>
      {model.description && <p className="mt-1 text-sm text-muted-foreground">{model.description}</p>}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="py-1.5 pr-3 font-semibold">Version</th>
              {metricKeys.map((k) => (
                <th key={k} className="py-1.5 pr-3 font-semibold">{k}</th>
              ))}
              <th className="py-1.5 pr-3 font-semibold">Lineage</th>
              <th className="py-1.5 pr-3 font-semibold">Aliases</th>
              <th className="py-1.5 pr-3 font-semibold text-right">Copy</th>
            </tr>
          </thead>
          <tbody>
            {model.versions.map((v) => (
              <tr key={v.version} className="border-b border-border/50 align-top">
                <td className="py-2 pr-3 font-medium">v{v.version}</td>
                {metricKeys.map((k) => (
                  <td key={k} className="py-2 pr-3 tabular-nums">
                    {k in v.metrics ? fmtMetric(v.metrics[k]) : <span className="text-muted-foreground">—</span>}
                  </td>
                ))}
                <td className="py-2 pr-3"><LineageChips lineage={v.lineage} flowName={flowName} /></td>
                <td className="py-2 pr-3"><AliasEditor model={model.name} version={v} /></td>
                <td className="py-2 pr-3">
                  <div className="flex items-center justify-end gap-1">
                    <CopyButton value={modelUri(model.name, v)} label="URI" />
                    {v.run_id && <CopyButton value={v.run_id} label="run id" />}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Prefer the alias URI when the version carries one, else a versioned URI. */
function modelUri(name: string, v: MlModelVersion): string {
  if (v.aliases.length) return `models:/${name}@${v.aliases[0]}`;
  return `models:/${name}/${v.version}`;
}

function AliasEditor({ model, version }: { model: string; version: MlModelVersion }) {
  const setAlias = useSetModelAlias();
  const clearAlias = useClearModelAlias();
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  // A single version can carry more than one alias (e.g. @production and
  // @champion both pointing at v3) — clearAlias.isPending alone would disable
  // every alias chip's clear button on this row while only one is clearing,
  // so track which specific alias names are in flight.
  const [clearingAliases, setClearingAliases] = useState<Set<string>>(new Set());

  const submit = () => {
    if (setAlias.isPending) return;
    const alias = value.trim();
    if (!alias) return;
    setAlias.mutate(
      { model, alias, version: version.version },
      { onSuccess: () => { setValue(""); setAdding(false); } },
    );
  };

  const clear = (alias: string) => {
    if (clearingAliases.has(alias)) return;
    setClearingAliases((prev) => new Set(prev).add(alias));
    clearAlias
      .mutateAsync({ model, alias })
      .catch(() => {})
      .finally(() => {
        setClearingAliases((prev) => {
          const next = new Set(prev);
          next.delete(alias);
          return next;
        });
      });
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {version.aliases.map((a) => (
        <span key={a} className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-1.5 py-0.5 text-[11px] font-medium text-purple-700">
          @{a}
          <button
            onClick={() => clear(a)}
            disabled={clearingAliases.has(a)}
            title={`Clear @${a}`}
            className="rounded-full hover:text-purple-900 disabled:pointer-events-none disabled:opacity-50"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      {adding ? (
        <span className="inline-flex items-center gap-1">
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); if (e.key === "Escape") setAdding(false); }}
            placeholder="production"
            className="h-6 w-24 rounded border border-input bg-background px-1.5 text-[11px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <button onClick={submit} disabled={setAlias.isPending} className="text-[11px] font-medium text-primary hover:underline">
            Set
          </button>
        </span>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-0.5 rounded-full border border-dashed border-border px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-muted"
        >
          <Plus className="h-3 w-3" /> alias
        </button>
      )}
    </div>
  );
}

// ─── Experiments leaderboard ────────────────────────────────────────────────

function ExperimentsTab({ flowName }: { flowName: Map<string, string> }) {
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
