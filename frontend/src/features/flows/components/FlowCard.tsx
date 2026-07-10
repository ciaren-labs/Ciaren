import { CalendarClock, Copy as CopyIcon, Loader2, Pencil, Play, Power, Trash2, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type { Flow } from "@/features/flows/types";

export function FlowCard({
  flow,
  isDuplicating,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
  onDuplicate,
}: {
  flow: Flow;
  isDuplicating: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onRun: () => void;
  onSchedule: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const fmt = useFormatDateTime();
  return (
    <div className={cn("group animate-fade-in-up flex flex-col rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md", flow.is_disabled ? "border-amber-300 opacity-70" : "border-border")}>
      <button onClick={onOpen} className="flex-1 text-left">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-brand-600" />
          <span className="truncate font-semibold">{flow.name}</span>
          {flow.is_disabled && (
            <span className="shrink-0 rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
              disabled
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
          {flow.description || "No description"}
        </p>
        <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{flow.graph_json?.nodes?.length ?? 0} nodes</span>
        </div>
        <div className="mt-1.5 flex flex-col gap-0.5 text-[11px] text-muted-foreground/80">
          <span>Created {fmt(flow.created_at)}</span>
          <span>{flow.last_run_at ? `Last run ${fmt(flow.last_run_at)}` : "Never run"}</span>
        </div>
      </button>
      <div className="mt-3 flex items-center justify-end gap-2 border-t border-border pt-2.5">
        <Button size="sm" variant="outline" onClick={onOpen}>
          Open
        </Button>
        <button
          onClick={onRun}
          disabled={flow.is_disabled}
          className="rounded-md p-2 text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700 disabled:pointer-events-none disabled:opacity-40"
          title="Run flow"
        >
          <Play className="h-4 w-4" />
        </button>
        <button
          onClick={onSchedule}
          disabled={flow.is_disabled}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          title="Schedule flow"
        >
          <CalendarClock className="h-4 w-4" />
        </button>
        <button
          onClick={onEdit}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Edit name & description"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          onClick={onToggle}
          className={cn(
            "rounded-md p-2 transition-colors hover:bg-muted",
            flow.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
          )}
          title={flow.is_disabled ? "Enable flow" : "Disable flow"}
        >
          <Power className="h-4 w-4" />
        </button>
        <button
          onClick={onDuplicate}
          disabled={isDuplicating}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          title="Duplicate flow (graph, parameters and engine — not schedules or history)"
        >
          {isDuplicating ? <Loader2 className="h-4 w-4 animate-spin" /> : <CopyIcon className="h-4 w-4" />}
        </button>
        <button
          onClick={onDelete}
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          title="Delete flow"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
