import { useMemo, useState } from "react";
import { Plus, Trophy, X } from "lucide-react";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { SearchableSelect } from "@/components/filters/SearchableSelect";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type { MlModelVersion, MlRegisteredModel } from "@/features/models/types";
import { useClearModelAlias, useRegisteredModels, useSetModelAlias } from "../hooks";
import { fmtMetric, headlineMetric, modelUri } from "./mlFormat";
import { CopyButton, EmptyBox, ErrorBox, Loading, LineageChips } from "./shared";

const NO_PROJECT = "__none__";

export function RegisteredModelsTab({
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
