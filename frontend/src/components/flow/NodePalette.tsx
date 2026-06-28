import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, ChevronRight, GripVertical, Lock, Search, X } from "lucide-react";
import { transformationsApi } from "@/lib/api";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  type NodeCategory,
  type NodeTypeDef,
} from "@/lib/nodeCatalog";
import { useNodeCatalog } from "@/features/flows/useNodeCatalog";
import { CATEGORY_ICONS, CATEGORY_THEME, getNodeIcon } from "@/lib/nodeVisuals";
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
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("ff_palette_collapsed") === "true";
  });

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("ff_palette_collapsed", String(next));
  };

  const toggle = (category: NodeCategory) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });

  // The palette is sourced from the backend catalog (which includes plugin nodes)
  // merged over the static seed; see useNodeCatalog.
  const catalog = useNodeCatalog();

  // The backend only lists ML node types when the ML extension is installed +
  // enabled. The catalog already reflects that, but keep this gate so the static
  // fallback (offline / failed fetch) still hides ML when it isn't available.
  const { data: availableTypes } = useQuery({
    queryKey: ["transformations", "available"],
    queryFn: () => transformationsApi.list(),
    staleTime: 5 * 60 * 1000,
  });
  const visibleTypes = useMemo(() => {
    const available = new Set(availableTypes ?? []);
    return catalog.filter((n) => !n.requiresMl || available.has(n.type));
  }, [catalog, availableTypes]);

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => {
    if (!q) return [];
    return visibleTypes.filter(
      (n) =>
        n.label.toLowerCase().includes(q) ||
        n.description.toLowerCase().includes(q) ||
        n.type.toLowerCase().includes(q),
    );
  }, [q, visibleTypes]);

  if (collapsed) {
    return (
      <div className="flex h-full w-10 shrink-0 flex-col items-center gap-3 border-r border-border bg-muted/30 py-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={toggleCollapsed}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Show nodes panel</TooltipContent>
        </Tooltip>

        <div className="flex flex-col gap-2">
          {CATEGORY_ORDER.map((cat) => {
            const CatIcon = CATEGORY_ICONS[cat];
            const theme = CATEGORY_THEME[cat];
            const locked = !unlocked && cat !== "input";
            return (
              <Tooltip key={cat}>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-md",
                      theme.badge,
                      locked && "opacity-40",
                    )}
                  >
                    <CatIcon className="h-3.5 w-3.5" />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="right">{CATEGORY_LABELS[cat]}</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-60 shrink-0 flex-col gap-2 overflow-y-auto border-r border-border bg-muted/30 p-3">
      <div className="flex items-start justify-between px-1">
        <div>
          <h2 className="text-base font-semibold text-foreground">Nodes</h2>
          <p className="text-xs text-muted-foreground">
            Drag onto the canvas, or click to add
          </p>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={toggleCollapsed}
              className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Collapse panel</TooltipContent>
        </Tooltip>
      </div>

      <div className="relative px-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search nodes…"
          className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-7 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {q ? (
        <div className="mt-1 flex flex-col gap-1 pl-1.5">
          {matches.length === 0 ? (
            <p className="px-1.5 py-2 text-xs text-muted-foreground">No nodes match "{query}".</p>
          ) : (
            matches.map((def) => (
              <PaletteItem
                key={def.type}
                def={def}
                disabled={!unlocked && def.category !== "input"}
                onAdd={onAdd}
              />
            ))
          )}
        </div>
      ) : (
        <PaletteAccordion
          unlocked={unlocked}
          open={open}
          toggle={toggle}
          onAdd={onAdd}
          nodeTypes={visibleTypes}
        />
      )}
    </div>
  );
}

function PaletteAccordion({
  unlocked,
  open,
  toggle,
  onAdd,
  nodeTypes,
}: {
  unlocked: boolean;
  open: Set<NodeCategory>;
  toggle: (category: NodeCategory) => void;
  onAdd: (def: NodeTypeDef) => void;
  nodeTypes: NodeTypeDef[];
}) {
  return (
    <>
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
        const items = nodeTypes.filter((n) => n.category === category);
        if (items.length === 0) return null;
        const isOpen = open.has(category);
        const locked = !unlocked && category !== "input";
        const CatIcon = CATEGORY_ICONS[category];
        const theme = CATEGORY_THEME[category];
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
              <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-md", theme.badge)}>
                <CatIcon className="h-3 w-3" />
              </span>
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
    </>
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
