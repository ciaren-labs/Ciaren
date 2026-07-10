import { EyeOff, Power, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Dataset } from "@/features/datasets/types";
import { SOURCE_META, versionLabel } from "./datasetMeta";

export function DatasetGrid({
  datasets,
  onSelect,
  onAction,
}: {
  datasets: Dataset[];
  onSelect: (d: Dataset) => void;
  onAction?: (d: Dataset, kind: "disable" | "enable" | "delete") => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {datasets.map((d) => (
        <DatasetCard key={d.id} dataset={d} onClick={() => onSelect(d)} onAction={onAction} />
      ))}
    </div>
  );
}

function DatasetCard({
  dataset: d,
  onClick,
  onAction,
}: {
  dataset: Dataset;
  onClick: () => void;
  onAction?: (d: Dataset, kind: "disable" | "enable" | "delete") => void;
}) {
  const meta = SOURCE_META[d.source_type] ?? SOURCE_META.csv;
  const Icon = meta.icon;
  const schema = d.column_schema ?? [];

  return (
    <div className={cn("group text-left", d.is_disabled && "opacity-70")}>
      <Card className="animate-fade-in-up h-full overflow-hidden transition-shadow hover:shadow-md">
        <button onClick={onClick} className="block w-full text-left">
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg text-white shadow-sm", meta.tint)}>
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <CardTitle className="truncate text-sm">{d.name}</CardTitle>
                {d.dataset_kind === "output" && (
                  <span className="shrink-0 rounded-md bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                    output
                  </span>
                )}
                {d.is_disabled && (
                  <span className="shrink-0 rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                    disabled
                  </span>
                )}
              </div>
              <CardDescription className="text-xs">
                {d.source_type.toUpperCase()} · {schema.length} columns ·{" "}
                {versionLabel(d.latest_version, d.version_count)}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {schema.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {schema.slice(0, 8).map((col) => (
                  <span
                    key={col.name}
                    className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                    title={`${col.name}: ${col.type}`}
                  >
                    {col.name}
                  </span>
                ))}
                {schema.length > 8 && (
                  <span className="rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    +{schema.length - 8} more
                  </span>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Schema unavailable.</p>
            )}
          </CardContent>
        </button>
        {onAction && (
          <div className="flex items-center justify-end gap-1 border-t border-border px-2 py-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <button
              onClick={() => onAction(d, d.is_disabled ? "enable" : "disable")}
              className={cn(
                "rounded-md p-1.5 transition-colors hover:bg-muted",
                d.is_disabled ? "text-amber-500 hover:text-amber-600" : "text-emerald-500 hover:text-emerald-600",
              )}
              title={d.is_disabled ? "Enable dataset" : "Disable dataset"}
            >
              {d.is_disabled ? <Power className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={() => onAction(d, "delete")}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              title="Delete dataset"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}
