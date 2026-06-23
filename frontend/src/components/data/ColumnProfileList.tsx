// Compact per-column statistics readout, shared by the flow editor's preview
// panel and the dataset detail dialog. Renders type-aware summaries from the
// backend profiler (app/engine/profile.py).
import type { ColumnProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

const DTYPE_STYLES: Record<ColumnProfile["dtype"], string> = {
  integer: "bg-blue-100 text-blue-700",
  float: "bg-blue-100 text-blue-700",
  boolean: "bg-purple-100 text-purple-700",
  datetime: "bg-amber-100 text-amber-700",
  string: "bg-slate-100 text-slate-600",
};

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-xs font-medium tabular-nums">{value}</span>
    </div>
  );
}

function fmt(value: number | string | null | undefined): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return value;
}

function ColumnCard({ p }: { p: ColumnProfile }) {
  const isNumeric = p.dtype === "integer" || p.dtype === "float";
  return (
    <div className="rounded-lg border border-border bg-card p-2.5">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="truncate text-xs font-semibold" title={p.name}>
          {p.name}
        </span>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", DTYPE_STYLES[p.dtype])}>
          {p.dtype}
        </span>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        <Stat label="Nulls" value={`${p.null_count} (${p.null_pct}%)`} />
        <Stat label="Distinct" value={p.distinct} />
        {isNumeric && (
          <>
            <Stat label="Min" value={fmt(p.min)} />
            <Stat label="Mean" value={fmt(p.mean)} />
            <Stat label="Max" value={fmt(p.max)} />
          </>
        )}
        {p.dtype === "datetime" && (
          <>
            <Stat label="Earliest" value={fmt(p.min)} />
            <Stat label="Latest" value={fmt(p.max)} />
          </>
        )}
        {p.dtype === "boolean" && p.true_count != null && (
          <Stat label="True" value={p.true_count} />
        )}
        {p.dtype === "string" && p.min_len != null && (
          <Stat label="Length" value={`${p.min_len}–${p.max_len}`} />
        )}
      </div>

      {p.dtype === "string" && p.top_values && p.top_values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {p.top_values.map((tv) => (
            <span
              key={tv.value}
              className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-slate-600"
              title={`${tv.value}: ${tv.count}`}
            >
              {tv.value} <span className="text-muted-foreground">×{tv.count}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function ColumnProfileList({ profile }: { profile: ColumnProfile[] }) {
  if (profile.length === 0) {
    return <p className="p-3 text-sm text-muted-foreground">No columns to profile.</p>;
  }
  const sampled = profile[0] && profile[0].scanned < profile[0].total;
  return (
    <div className="flex flex-col gap-1.5 p-2">
      {sampled && (
        <p className="px-1 text-[11px] text-muted-foreground">
          Statistics computed on the first {profile[0].scanned.toLocaleString()} of{" "}
          {profile[0].total.toLocaleString()} rows.
        </p>
      )}
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {profile.map((p) => (
          <ColumnCard key={p.name} p={p} />
        ))}
      </div>
    </div>
  );
}
