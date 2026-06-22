import { useState } from "react";
import { ChevronDown, GripVertical, Lock } from "lucide-react";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  NODE_TYPES,
  type NodeCategory,
  type NodeTypeDef,
} from "@/lib/nodeCatalog";
import { getNodeIcon } from "@/lib/nodeVisuals";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/** MIME-ish key used to carry the node type across a drag from palette → canvas. */
export const NODE_DND_MIME = "application/flowframe-node";

interface NodePaletteProps {
  onAdd: (def: NodeTypeDef) => void;
  /** When false, every non-input category is locked until a dataset is set. */
  unlocked: boolean;
}

export function NodePalette({ onAdd, unlocked }: NodePaletteProps) {
  // Accordion: all sections collapsed by default per design.
  const [open, setOpen] = useState<Set<NodeCategory>>(new Set());

  const toggle = (category: NodeCategory) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });

  return (
    <div className="flex h-full w-60 flex-col gap-2 overflow-y-auto border-r border-border bg-muted/30 p-3">
      <div className="px-1">
        <h2 className="text-base font-semibold text-foreground">Nodes</h2>
        <p className="text-xs text-muted-foreground">
          Drag onto the canvas, or click to add
        </p>
      </div>

      {!unlocked && (
        <div className="animate-fade-in flex items-start gap-2 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-2 text-[11px] leading-snug text-brand-800">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Start with an <strong>Input</strong> and pick a dataset to unlock the
            other nodes.
          </span>
        </div>
      )}

      {CATEGORY_ORDER.map((category) => {
        const items = NODE_TYPES.filter((n) => n.category === category);
        const isOpen = open.has(category);
        const locked = !unlocked && category !== "input";
        return (
          <div key={category} className="flex flex-col">
            <button
              type="button"
              onClick={() => toggle(category)}
              className={cn(
                "flex items-center gap-2 rounded-md px-1.5 py-2 text-left transition-colors hover:bg-muted",
                locked && "opacity-60",
              )}
            >
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform duration-150",
                  isOpen && "rotate-0",
                  !isOpen && "-rotate-90",
                )}
              />
              <span className="flex-1 text-sm font-semibold text-foreground">
                {CATEGORY_LABELS[category]}
              </span>
              {locked && <Lock className="h-3.5 w-3.5 text-muted-foreground" />}
              <span className="text-xs tabular-nums text-muted-foreground/70">
                {items.length}
              </span>
            </button>

            {isOpen && (
              <div className="mt-1 flex flex-col gap-1 pl-1.5">
                {items.map((def) => (
                  <PaletteItem key={def.type} def={def} disabled={locked} onAdd={onAdd} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PaletteItem({
  def,
  disabled,
  onAdd,
}: {
  def: NodeTypeDef;
  disabled: boolean;
  onAdd: (def: NodeTypeDef) => void;
}) {
  const Icon = getNodeIcon(def.type);
  return (
    <Tooltip delayDuration={300}>
      <TooltipTrigger asChild>
        <button
          draggable={!disabled}
          onDragStart={(e) => {
            if (disabled) return;
            e.dataTransfer.setData(NODE_DND_MIME, def.type);
            e.dataTransfer.effectAllowed = "move";
          }}
          onClick={() => !disabled && onAdd(def)}
          disabled={disabled}
          className={cn(
            "group flex items-center gap-2.5 rounded-lg border border-transparent bg-card/60 px-2.5 py-2 text-left text-sm font-medium text-slate-700 shadow-sm",
            "transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            disabled
              ? "cursor-not-allowed opacity-50"
              : "cursor-grab hover:-translate-y-px hover:border-brand-200 hover:bg-card hover:shadow active:cursor-grabbing",
          )}
        >
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-brand-600 transition-transform group-hover:scale-105">
            <Icon className="h-3.5 w-3.5" strokeWidth={2.25} />
          </span>
          <span className="flex-1 truncate">{def.label}</span>
          {!disabled && (
            <GripVertical className="h-4 w-4 text-muted-foreground/40 opacity-0 transition-opacity group-hover:opacity-100" />
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">
        {disabled ? "Set a dataset on an input node first" : def.description}
      </TooltipContent>
    </Tooltip>
  );
}
