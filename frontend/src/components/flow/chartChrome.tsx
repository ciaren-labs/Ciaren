// Shared chart chrome: the recessive axis/grid/tooltip/legend styling and the
// number/date formatters used by every chart in the app. Extracted from
// ChartPreview so the run-screen chart renderer (RunChart) draws with exactly
// the same visual language as the preview charts.
import { ResponsiveContainer } from "recharts";
import { toNumber } from "@/lib/chartData";
import type { ChartTheme } from "@/lib/chartTheme";

export const compact = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});
export const full = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

export function fmtTick(v: unknown): string {
  const n = toNumber(v);
  return n === null ? String(v ?? "") : compact.format(n);
}

export function fmtValue(v: unknown): string {
  const n = toNumber(v);
  return n === null ? String(v ?? "") : full.format(n);
}

/** Trim ISO datetime axis labels: "2023-01-08T00:00:00.000" → "2023-01-08". */
export function fmtCategory(v: unknown): string {
  const s = String(v ?? "");
  const iso = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(s);
  if (!iso) return s;
  return iso[2] === "00:00" ? iso[1] : `${iso[1]} ${iso[2]}`;
}

/** Recessive axis: muted tick text, hairline axis rule, no tick marks. */
export function axisProps(t: ChartTheme) {
  return {
    tick: { fontSize: 10, fill: t.axis },
    axisLine: { stroke: t.grid },
    tickLine: false as const,
  };
}

export function gridProps(t: ChartTheme) {
  // Solid hairlines, horizontal only — the grid must stay recessive.
  return { vertical: false, stroke: t.grid };
}

export function tooltipProps(t: ChartTheme) {
  return {
    cursor: { fill: t.cursor },
    contentStyle: {
      backgroundColor: t.tooltipBg,
      border: `1px solid ${t.tooltipBorder}`,
      borderRadius: 8,
      fontSize: 11,
      padding: "6px 10px",
      boxShadow: "0 4px 12px rgba(0,0,0,0.10)",
    },
    labelStyle: { color: t.ink, fontWeight: 600, marginBottom: 2 },
    itemStyle: { color: t.ink, padding: 0 },
  };
}

export function legendProps(t: ChartTheme) {
  return {
    iconType: "circle" as const,
    iconSize: 8,
    // Legend text wears ink, not the series colour — the swatch carries identity.
    formatter: (value: string) => <span style={{ color: t.axis, fontSize: 11 }}>{value}</span>,
  };
}

export function ChartFrame({ children }: { children: React.ReactElement }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

export function Placeholder({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border bg-muted/40 p-4 text-center text-xs text-muted-foreground">
      {children}
    </div>
  );
}
