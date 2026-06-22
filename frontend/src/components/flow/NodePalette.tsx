import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  NODE_TYPES,
  type NodeTypeDef,
} from "@/lib/nodeCatalog";
import { CATEGORY_THEME, getNodeIcon } from "@/lib/nodeVisuals";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface NodePaletteProps {
  onAdd: (def: NodeTypeDef) => void;
}

export function NodePalette({ onAdd }: NodePaletteProps) {
  return (
    <div className="flex h-full w-56 flex-col gap-4 overflow-y-auto border-r border-border bg-muted/30 p-3">
      <div className="px-1">
        <h2 className="text-sm font-semibold text-foreground">Nodes</h2>
        <p className="text-[11px] text-muted-foreground">Click to add to the canvas</p>
      </div>

      {CATEGORY_ORDER.map((category) => {
        const items = NODE_TYPES.filter((n) => n.category === category);
        const theme = CATEGORY_THEME[category];
        return (
          <div key={category} className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 px-1">
              <span className={cn("h-2 w-2 rounded-full", theme.dot)} />
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {CATEGORY_LABELS[category]}
              </span>
            </div>
            <div className="flex flex-col gap-1">
              {items.map((def) => {
                const Icon = getNodeIcon(def.type);
                return (
                  <Tooltip key={def.type} delayDuration={300}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => onAdd(def)}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-lg border border-transparent bg-card/60 px-2.5 py-2 text-left text-xs font-medium text-slate-700 shadow-sm",
                          "transition-all duration-150 hover:-translate-y-px hover:border-border hover:bg-card hover:shadow",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        )}
                      >
                        <span
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-transform group-hover:scale-105",
                            theme.badge,
                          )}
                        >
                          <Icon className="h-3.5 w-3.5" strokeWidth={2.25} />
                        </span>
                        <span className="truncate">{def.label}</span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="right">{def.description}</TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
