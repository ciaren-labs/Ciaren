import { CalendarClock, Copy as CopyIcon, Loader2, Pencil, Play, Power, Trash2 } from "lucide-react";
import { SortableTh, type SortState } from "@/components/ui/SortableHeader";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type { Flow } from "@/features/flows/types";

export type FlowSortKey = "name" | "nodes" | "status" | "created" | "last_run";

export const FLOW_SORT: Record<FlowSortKey, (f: Flow) => string | number | null> = {
  name: (f) => f.name.toLowerCase(),
  nodes: (f) => f.graph_json?.nodes?.length ?? 0,
  status: (f) => (f.is_disabled ? "disabled" : "active"),
  created: (f) => f.created_at,
  last_run: (f) => f.last_run_at ?? null,
};

export function FlowTable({
  flows,
  sort,
  onSort,
  isDuplicating,
  onOpen,
  onEdit,
  onRun,
  onSchedule,
  onToggle,
  onDelete,
  onDuplicate,
}: {
  flows: Flow[];
  sort: SortState<FlowSortKey>;
  onSort: (key: FlowSortKey) => void;
  isDuplicating: (flow: Flow) => boolean;
  onOpen: (id: string) => void;
  onEdit: (flow: Flow) => void;
  onRun: (flow: Flow) => void;
  onSchedule: (flow: Flow) => void;
  onToggle: (flow: Flow) => void;
  onDelete: (flow: Flow) => void;
  onDuplicate: (flow: Flow) => void;
}) {
  const fmt = useFormatDateTime();
  if (flows.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <SortableTh label="Name" sortKey="name" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Nodes" sortKey="nodes" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Status" sortKey="status" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Created" sortKey="created" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <SortableTh label="Last run" sortKey="last_run" sort={sort} onSort={onSort} className="px-4 py-2.5 text-left" />
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {flows.map((flow) => {
            return (
              <tr
                key={flow.id}
                className={cn("border-t border-border hover:bg-accent/40 transition-colors", flow.is_disabled && "bg-amber-50/30 opacity-70")}
              >
                <td className="px-4 py-2.5">
                  <button onClick={() => onOpen(flow.id)} className="font-medium hover:underline">
                    {flow.name}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {flow.graph_json?.nodes?.length ?? 0}
                </td>
                <td className="px-4 py-2.5">
                  {flow.is_disabled ? (
                    <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                      disabled
                    </span>
                  ) : (
                    <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                      active
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">{fmt(flow.created_at)}</td>
                <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                  {flow.last_run_at ? fmt(flow.last_run_at) : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => onRun(flow)}
                      disabled={flow.is_disabled}
                      className="rounded-md p-1.5 text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700 disabled:pointer-events-none disabled:opacity-40"
                      title="Run flow"
                    >
                      <Play className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onSchedule(flow)}
                      disabled={flow.is_disabled}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      title="Schedule flow"
                    >
                      <CalendarClock className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onEdit(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      title="Edit"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onToggle(flow)}
                      className={cn(
                        "rounded-md p-1.5 transition-colors hover:bg-muted",
                        flow.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
                      )}
                      title={flow.is_disabled ? "Enable" : "Disable"}
                    >
                      <Power className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onDuplicate(flow)}
                      disabled={isDuplicating(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
                      title="Duplicate"
                    >
                      {isDuplicating(flow) ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <CopyIcon className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <button
                      onClick={() => onDelete(flow)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
