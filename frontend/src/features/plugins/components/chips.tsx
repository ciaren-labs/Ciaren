import { cn } from "@/lib/utils";
import { getCategoryLabel } from "@/lib/nodeCatalog";
import { getCategoryTheme } from "@/lib/nodeVisuals";

/** Shows the node types a plugin contributes and where they land in the palette.
 *  Shared by the installed-plugin detail dialog and the marketplace card. */
export function NodePlacement({
  nodes,
  nodeCategories,
}: {
  nodes: string[];
  nodeCategories: Record<string, string>;
}) {
  if (nodes.length === 0) return null;
  return (
    <div className="mt-2.5">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Appears as node
      </p>
      <div className="flex flex-wrap gap-1">
        {nodes.map((node) => {
          const category = nodeCategories[node] ?? "plugins";
          const theme = getCategoryTheme(category);
          return (
            <span
              key={node}
              className="inline-flex items-center overflow-hidden rounded-md border border-border bg-background text-[10px] shadow-sm"
            >
              <span className="px-1.5 py-0.5 font-mono text-slate-700">{node}</span>
              <span className={cn("border-l border-border px-1.5 py-0.5 font-medium", theme.text)}>
                {getCategoryLabel(category)}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

export function ContributionChips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2.5">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-slate-700 shadow-sm"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
