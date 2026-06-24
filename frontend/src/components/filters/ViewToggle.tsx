import { LayoutGrid, List } from "lucide-react";
import { cn } from "@/lib/utils";

export type ViewLayout = "table" | "cards";

/** Shared table/cards switch so every list page shows it identically (same order,
 * icons, and placement — the header's right cluster). Table first, then cards. */
export function ViewToggle({
  value,
  onChange,
}: {
  value: ViewLayout;
  onChange: (v: ViewLayout) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
      <button
        type="button"
        onClick={() => onChange("table")}
        className={cn(
          "rounded p-1.5 transition-colors",
          value === "table" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
        title="Table view"
        aria-label="Table view"
      >
        <List className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => onChange("cards")}
        className={cn(
          "rounded p-1.5 transition-colors",
          value === "cards" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
        title="Card view"
        aria-label="Card view"
      >
        <LayoutGrid className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
