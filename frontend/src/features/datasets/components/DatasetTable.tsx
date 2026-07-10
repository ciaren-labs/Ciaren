import { EyeOff, Power, Trash2 } from "lucide-react";
import { SortableTh, type SortState } from "@/components/ui/SortableHeader";
import { useFormatDateTime } from "@/lib/useFormatDateTime";
import { cn } from "@/lib/utils";
import type { Dataset } from "@/features/datasets/types";
import { versionLabel, type DatasetSortKey } from "./datasetMeta";

export function DatasetTable({
  datasets,
  sort,
  onSort,
  onSelect,
  onAction,
}: {
  datasets: Dataset[];
  sort: SortState<DatasetSortKey>;
  onSort: (key: DatasetSortKey) => void;
  onSelect: (d: Dataset) => void;
  onAction?: (d: Dataset, kind: "disable" | "enable" | "delete") => void;
}) {
  const fmtDate = useFormatDateTime();
  const thClass = "border-b border-border px-3 py-2 text-left font-semibold";
  return (
    <div className="overflow-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-muted uppercase tracking-wide text-muted-foreground">
          <tr>
            <SortableTh label="Name" sortKey="name" sort={sort} onSort={onSort} className={thClass} />
            <th className={thClass}>Type</th>
            <th className={thClass}>Kind</th>
            <SortableTh label="Columns" sortKey="columns" sort={sort} onSort={onSort} className={thClass} />
            <SortableTh label="Versions" sortKey="versions" sort={sort} onSort={onSort} className={thClass} />
            <SortableTh label="Created" sortKey="created" sort={sort} onSort={onSort} className={thClass} />
            {onAction && <th className="border-b border-border px-3 py-2" />}
          </tr>
        </thead>
        <tbody>
          {datasets.map((d) => (
            <tr
              key={d.id}
              className={cn(
                "odd:bg-background even:bg-muted/30 hover:bg-accent/40 transition-colors",
                d.is_disabled && "bg-amber-50/20 opacity-70",
              )}
            >
              <td
                className="border-b border-border px-3 py-2 font-medium cursor-pointer"
                onClick={() => onSelect(d)}
              >
                {d.name}
                {d.is_disabled && (
                  <span className="ml-1.5 rounded bg-amber-100 px-1 py-0.5 text-[10px] font-semibold text-amber-700">
                    disabled
                  </span>
                )}
              </td>
              <td className="border-b border-border px-3 py-2 uppercase text-muted-foreground cursor-pointer" onClick={() => onSelect(d)}>{d.source_type}</td>
              <td className="border-b border-border px-3 py-2 cursor-pointer" onClick={() => onSelect(d)}>
                {d.dataset_kind === "output" ? (
                  <span className="rounded-md bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                    output
                  </span>
                ) : (
                  <span className="text-muted-foreground">upload</span>
                )}
              </td>
              <td className="border-b border-border px-3 py-2 text-muted-foreground cursor-pointer" onClick={() => onSelect(d)}>
                {d.column_schema?.length ?? 0}
              </td>
              <td className="border-b border-border px-3 py-2 text-muted-foreground cursor-pointer" onClick={() => onSelect(d)}>
                {versionLabel(d.latest_version, d.version_count)}
              </td>
              <td className="border-b border-border px-3 py-2 text-muted-foreground cursor-pointer whitespace-nowrap" onClick={() => onSelect(d)}>
                {fmtDate(d.created_at)}
              </td>
              {onAction && (
                <td className="border-b border-border px-3 py-2">
                  <div className="flex items-center gap-1 justify-end">
                    <button
                      onClick={() => onAction(d, d.is_disabled ? "enable" : "disable")}
                      className={cn(
                        "rounded p-1 transition-colors hover:bg-muted",
                        d.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
                      )}
                      title={d.is_disabled ? "Enable dataset" : "Disable dataset"}
                    >
                      {d.is_disabled ? <Power className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                    </button>
                    <button
                      onClick={() => onAction(d, "delete")}
                      className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                      title="Delete dataset"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
