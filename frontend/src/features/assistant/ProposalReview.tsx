import type { Dataset } from "@/features/datasets/types";
import type { GraphJson, GraphNode } from "@/features/flows/types";
import type { Delta } from "./api";

function settings(node: GraphNode, datasets: Dataset[]) {
  const c = node.data.config;
  const columns = (field: unknown) =>
    Array.isArray(field) && field.length ? field.join(", ") : "all columns";
  switch (node.type) {
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
      return JSON.stringify(c);
    }
    case "fileInput":
      return `${datasets.find((d) => d.id === c.dataset_id)?.name ?? "Selected dataset"} · version ${c.dataset_version}`;
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
      return JSON.stringify(c);
  }
}

export function ProposalReview({
  delta,
  base,
  datasets,
}: {
  delta: Delta;
  base: GraphJson;
  datasets: Dataset[];
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
    <section
      aria-label="Proposed changes"
      className="space-y-3 rounded-lg border border-border bg-card p-4 text-sm"
    >
      <h3 className="font-semibold">Proposed changes</h3>
      <ul className="divide-y divide-border">
        {[...delta.added, ...delta.changed].map((n) => {
          const old = base.nodes.find((existing) => existing.id === n.id);
          return (
            <li key={n.id} className="py-2">
              <span className="font-medium">
                {old ? "Update" : "Add"} {n.data.label}
              </span>
              <p className="break-words text-xs text-muted-foreground">
                {old && <>{settings(old, datasets)} → </>}
                {settings(n, datasets)}
              </p>
              {old && (
                <details className="mt-1 text-xs">
                  <summary className="cursor-pointer">
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
            </li>
          );
        })}
      </ul>
      <ul className="space-y-1 text-xs">
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
            {["left", "right"].includes(e.targetHandle ?? "") &&
              ` · ${e.targetHandle} input`}
          </li>
        ))}
      </ul>
      {[...delta.added, ...delta.changed].some((n) => n.type === "join") && (
        <p className="text-xs text-muted-foreground">
          Duplicate keys can produce multiple rows. Empty keys can match in
          pandas and stay unmatched in Polars.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Applying also saves your current canvas edits. Undo restores the
        previous canvas.
      </p>
    </section>
  );
}
