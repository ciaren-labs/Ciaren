import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  NODE_TYPES,
  type NodeTypeDef,
} from "@/lib/nodeCatalog";
import { Button } from "@/components/ui/button";

interface NodePaletteProps {
  onAdd: (def: NodeTypeDef) => void;
}

export function NodePalette({ onAdd }: NodePaletteProps) {
  return (
    <div className="flex h-full w-52 flex-col gap-3 overflow-y-auto border-r border-border bg-muted/40 p-3">
      <h2 className="text-sm font-semibold">Nodes</h2>
      {CATEGORY_ORDER.map((category) => {
        const items = NODE_TYPES.filter((n) => n.category === category);
        return (
          <div key={category} className="flex flex-col gap-1">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {CATEGORY_LABELS[category]}
            </div>
            {items.map((def) => (
              <Button
                key={def.type}
                variant="outline"
                size="sm"
                className="justify-start text-xs"
                title={def.description}
                onClick={() => onAdd(def)}
              >
                {def.label}
              </Button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
