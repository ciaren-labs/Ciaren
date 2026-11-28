import type { Dataset } from "@/features/datasets/types";
import type { GraphJson, GraphNode } from "@/features/flows/types";
import type { Delta } from "./api";

import { getNodeSummary } from "@/lib/nodeSummary";

import { FlowMap } from "./FlowMap";
import { nodeMark } from "./nodePresentation";
import { deltaCounts, summarize } from "./changeSummary";

function settings(node: GraphNode, datasets: Dataset[]) {
  const c = node.data.config;
  const columns = (field: unknown) =>
    Array.isArray(field) && field.length ? field.join(", ") : "all columns";
  switch (node.type) {
    case "trainTestSplit":
      return `Test ${Number(c.test_size) * 100}% · seed ${c.seed}`;
    case "mlTrainRegressor":
      return `${c.model_type} · ${c.target_column} from ${columns(c.feature_columns)}`;
    case "mlPredict":
      return `Score held-out rows into ${c.output_column}`;
    case "mlEvaluate":
      return `Compare ${c.target_column} with ${c.prediction_column} · ${columns(c.metrics)}`;
    case "join":
      return `${c.how ?? "inner"} Join · key ${[c.on].flat().join(", ")}`;
    case "conditionalColumn": {
      const rule = Array.isArray(c.rules) ? c.rules[0] : undefined;
      if (
        rule?.operator === "==" &&
        rule.result === true &&
        c.default === false
      ) {
        return `${c.new_column} is true when ${rule.column} equals “${rule.value}”, otherwise false`;
      }
      return fallback(node, datasets);
    }
    // Expressions are shown whole: the reviewer reads them before saving.
    case "calculatedColumn":
      return `${c.column_name} = ${c.expression}`;
    case "filterExpression":
      return `Keep rows where ${c.expression}`;
    case "assertExpression":
      return `Check that ${c.expression}`;
    case "fileInput": {
      const name = datasets.find((d) => d.id === c.dataset_id)?.name ?? "Selected dataset";
      return c.dataset_version == null ? `${name} · latest version` : `${name} · version ${c.dataset_version}`;
    }
    case "fileOutput":
      return `${String(c.format).toUpperCase()} · publish dataset “${c.dataset_name}” on run`;
    case "limitRows":
      return `${c.n} rows · skip ${c.offset ?? 0}`;
    case "selectColumns":
    case "dropColumns":
      return columns(c.columns);
    case "filterRows":
      return [c.column, c.operator, c.value].filter((v) => v != null).join(" ");
    case "sortRows":
      return `${columns(c.columns)} · ${c.ascending === false ? "descending" : "ascending"}`;
    case "dropNulls":
      return `Check ${columns(c.subset)} · drop if ${c.how ?? "any"} null`;
    case "removeDuplicates":
      return `Compare ${columns(c.subset)} · keep ${c.keep ?? "first"}`;
    default:
      return fallback(node, datasets);
  }
}

/** The editor's canvas subtitle, or the configured fields in words. */
function fallback(node: GraphNode, datasets: Dataset[]) {
  const c = node.data.config;
  const datasetName = datasets.find((d) => d.id === c.dataset_id)?.name;
  const summary = getNodeSummary(node.type, c, { datasetName });
  if (summary) return summary;
  const fields = Object.entries(c)
    .filter(([, v]) => v != null && v !== "" && !(Array.isArray(v) && v.length === 0))
    .slice(0, 4)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" ? "custom" : String(v)}`);
  return fields.length ? fields.join(" · ") : "Default settings";
}

export function ProposalReview({
  delta,
  base,
  datasets,
  inspectNode,
  headingId,
  compact = false,
}: {
  inspectNode: (id: string) => void;
  delta: Delta;
  base: GraphJson;
  datasets: Dataset[];
  headingId?: string;
  /** Summary only, for proposals that can no longer be applied. */
  compact?: boolean;
}) {
  const byId = new Map(
    [...base.nodes, ...delta.added].map((n) => [n.id, n.data.label]),
  );
  const allNodes = [...base.nodes, ...delta.added];
  function endpoint(id: string) {
    const n = allNodes.find((node) => node.id === id);
    return n?.type === "fileInput" ? settings(n, datasets) : byId.get(id);
  }
  return (
    <section aria-label="Proposed changes" className="space-y-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-1">
        <h3
          id={headingId}
          tabIndex={-1}
          className="text-base font-semibold tracking-tight focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Proposed changes
        </h3>
        <p className="text-xs text-muted-foreground">
          {summarize(deltaCounts(delta, base))}
        </p>
      </div>
      {!compact && (
        <>
      <FlowMap delta={delta} base={base} />
      <ul className="divide-y divide-border rounded-xl border border-border bg-card px-3">
        {[...delta.added, ...delta.changed].map((n) => {
          const old = base.nodes.find((existing) => existing.id === n.id);
          const { Icon, color } = nodeMark(n.type);
          return (
            <li key={n.id} className="flex gap-3 py-2.5">
              <span
                className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted ${color}`}
              >
                <Icon aria-hidden className="size-4" />
              </span>
              <div className="min-w-0">
                <span className="font-medium">
                  {old ? "Update" : "Add"} {n.data.label}
                </span>
                <p className="break-words text-xs text-muted-foreground">
                  {old && <>{settings(old, datasets)} → </>}
                  {settings(n, datasets)}
                </p>
                {old && (
                  <button
                    type="button"
                    className="mt-1 inline-flex min-h-8 items-center text-xs font-medium text-primary underline"
                    onClick={() => inspectNode(n.id)}
                  >
                    Inspect on canvas
                  </button>
                )}
                {old && (
                  <details className="mt-1 text-xs">
                    <summary className="inline-flex min-h-8 cursor-pointer items-center">
                      Compare all settings
                    </summary>
                    <p className="mt-2 font-medium">Before</p>
                    <pre className="whitespace-pre-wrap break-all">
                      {JSON.stringify(old.data.config, null, 2)}
                    </pre>
                    <p className="mt-2 font-medium">After</p>
                    <pre className="whitespace-pre-wrap break-all">
                      {JSON.stringify(n.data.config, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </li>
          );
        })}
        {delta.removed?.map((id) => {
          const old = base.nodes.find((n) => n.id === id);
          if (!old) return null;
          const { Icon } = nodeMark(old.type);
          return (
            <li key={id} className="flex gap-3 py-2.5">
              <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-destructive">
                <Icon aria-hidden className="size-4" />
              </span>
              <div className="min-w-0">
                <span className="font-medium">Remove {old.data.label}</span>
                <p className="break-words text-xs text-muted-foreground">
                  {settings(old, datasets)} · its connections go too
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      {delta.connected.length + delta.disconnected.length > 0 && (
        <details className="rounded-lg border border-border bg-card px-3 py-2.5">
          <summary className="flex min-h-8 cursor-pointer items-center text-xs font-semibold">
            Connections ({delta.connected.length + delta.disconnected.length})
          </summary>
          <ul className="mt-2 space-y-1 text-xs">
            {delta.disconnected.map((id) => {
              const e = base.edges.find((edge) => edge.id === id);
              return (
                e && (
                  <li key={id}>
                    Disconnect {byId.get(e.source)} → {byId.get(e.target)}
                  </li>
                )
              );
            })}
            {delta.connected.map((e) => (
              <li key={e.id}>
                Connect {endpoint(e.source)} → {byId.get(e.target)}
                {["train", "test", "model"].includes(e.sourceHandle ?? "") &&
                  ` · ${e.sourceHandle} output`}
                {["left", "right", "model"].includes(e.targetHandle ?? "") &&
                  ` · ${e.targetHandle} input`}
              </li>
            ))}
          </ul>
        </details>
      )}
      {[...delta.added, ...delta.changed].some((n) => n.type === "join") && (
        <details className="text-xs text-muted-foreground">
          <summary className="flex min-h-8 cursor-pointer items-center font-medium">
            Join behavior
          </summary>
          <p className="mt-1">
            Duplicate keys can produce multiple rows. Empty keys can match in
            pandas and stay unmatched in Polars.
          </p>
        </details>
      )}
      {delta.added.some((n) => n.type === "mlTrainRegressor") && (
        <p className="text-xs text-muted-foreground">
          Both joins keep matching orders. Run needs at least 13 matched rows
          with usable targets for the 80/20 split. Training logs the model and a feature sample to your configured MLflow
          store.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Applying saves this proposal to the flow.
      </p>
        </>
      )}
    </section>
  );
}
