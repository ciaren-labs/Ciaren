import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { projectColor } from "@/lib/projectColors";
import { cn } from "@/lib/utils";

/**
 * The single, shared "long horizontal" collapsible section used for project (and
 * other) grouping across pages — datasets, runs, models, schedules. A full-width
 * header bar with a chevron, an optional project colour dot, the title, and an
 * optional count badge; the children collapse below it. Uncontrolled by default
 * (keep open/closed per section without page-level state); keyed by the caller so
 * the open state survives re-renders/filtering.
 */
export function CollapsibleSection({
  title,
  colorKey,
  showDot = true,
  count,
  defaultOpen = true,
  children,
}: {
  title: string;
  /** Project colour key for the accent dot (ignored when showDot is false). */
  colorKey?: string | null;
  /** Hide the dot for non-project groups like "No project". */
  showDot?: boolean;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const theme = projectColor(colorKey);
  return (
    <section className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-left transition-colors hover:bg-muted/70"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        {showDot && <span className={cn("h-2.5 w-2.5 rounded-full", theme.dot)} />}
        <span className="flex-1 text-sm font-semibold">{title}</span>
        {count !== undefined && (
          <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {count}
          </span>
        )}
      </button>
      {open && children}
    </section>
  );
}
