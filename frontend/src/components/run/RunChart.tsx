// Renders a chart node's stored artifact on the run screen. The backend chart
// nodes compute render-ready, size-capped data over the FULL run data at run
// time and store it on the run's NodeResult, so opening a run never recomputes
// anything — this component only maps that JSON onto recharts (or a small
// custom SVG for the box plot / heatmap, which recharts doesn't offer).
//
// Everything here renders inside a single <svg>, which is what makes the
// "Export PNG" button work: the SVG is serialized onto a canvas together with a
// drawn title and legend (recharts' HTML legend wouldn't survive serialization).
import { useMemo, useRef } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { Download } from "lucide-react";
import {
  axisProps,
  ChartFrame,
  compact,
  fmtCategory,
  fmtTick,
  fmtValue,
  full,
  gridProps,
  legendProps,
  Placeholder,
  tooltipProps,
} from "@/components/flow/chartChrome";
import { clamp } from "@/lib/chartData";
import { inkForFill, mixHex, useChartTheme, type ChartTheme } from "@/lib/chartTheme";
import type { BoxGroupStats, ChartArtifact, NodeResult } from "@/features/runs/types";

const OTHER_LABEL = "Other";

/** Series colour by fixed slot; the "Other" bucket always wears neutral. */
function seriesColor(name: string, i: number, t: ChartTheme): string {
  return name === OTHER_LABEL ? t.neutral : t.series[i % t.series.length];
}

/** Legend entries drawn onto the exported PNG (charts with one series need none). */
export function exportLegendEntries(art: ChartArtifact, t: ChartTheme): { label: string; color: string }[] {
  if (art.kind === "pie") {
    // Must match Donut's null filter: an invisible slice would shift every
    // colour slot and make the exported legend disagree with the chart.
    return (art.data ?? [])
      .filter((d) => d.value !== null)
      .map((d, i) => ({ label: d.label, color: seriesColor(d.label, i, t) }));
  }
  const series = art.series ?? [];
  if ((art.kind === "bar" && art.group_by) || art.kind === "line" || art.kind === "area") {
    if (art.kind === "bar" || series.length > 1) {
      return series.map((s, i) => ({ label: s, color: seriesColor(s, i, t) }));
    }
  }
  return [];
}

/** A short "what was computed" line: "sum(amount) by region · 12,340 rows". */
function artifactSubtitle(art: ChartArtifact): string {
  const rows = art.rows_seen != null ? `${full.format(art.rows_seen)} rows` : "";
  const measure =
    art.aggregate === "count" || (!art.y && !art.value)
      ? "count"
      : `${art.aggregate}(${art.y ?? art.value ?? ""})`;
  let what = "";
  switch (art.kind) {
    case "bar":
      what = `${measure} by ${art.x}${art.group_by ? ` / ${art.group_by}` : ""}`;
      break;
    case "line":
    case "area":
      what = `${(art.series ?? []).join(", ")} by ${art.x}`;
      break;
    case "scatter":
      what = `${art.y} vs ${art.x}`;
      break;
    case "pie":
      what = `${measure} by ${art.category}`;
      break;
    case "histogram":
      what = `${art.column}`;
      break;
    case "boxplot":
      what = art.group_by ? `${art.column} by ${art.group_by}` : `${art.column}`;
      break;
    case "heatmap":
      what = `${(art.columns ?? []).length} columns`;
      break;
  }
  return [what, rows].filter(Boolean).join(" · ");
}

/** Truncation note when the artifact was capped ("top 25 of 118 categories"). */
function truncationNote(art: ChartArtifact): string | null {
  const notes: string[] = [];
  const shownCats = art.data?.length ?? art.rows?.length ?? 0;
  if (art.total_categories != null && art.total_categories > shownCats) {
    notes.push(
      art.kind === "pie"
        ? `top ${shownCats - 1} of ${art.total_categories} categories + Other`
        : `top ${shownCats}${art.data?.some((d) => d.label === OTHER_LABEL) ? " incl. Other" : ""} of ${art.total_categories} categories`,
    );
  }
  if (art.total_series != null && (art.series?.length ?? 0) < art.total_series) {
    notes.push(`${art.series?.length} of ${art.total_series} series`);
  }
  if (art.total_points != null) {
    const shown = art.points?.length ?? art.rows?.length ?? 0;
    if (shown < art.total_points) notes.push(`${full.format(shown)} of ${full.format(art.total_points)} points`);
  }
  if (art.total_groups != null && (art.groups?.length ?? 0) < art.total_groups) {
    notes.push(`largest ${art.groups?.length} of ${art.total_groups} groups`);
  }
  if (art.total_columns != null && (art.columns?.length ?? 0) < art.total_columns) {
    notes.push(`first ${art.columns?.length} of ${art.total_columns} numeric columns`);
  }
  const showing = notes.length ? `Showing ${notes.join("; ")}.` : null;
  if (art.dropped_columns?.length) {
    const dropped = `${art.dropped_columns.join(", ")} ${art.dropped_columns.length === 1 ? "was" : "were"} skipped (not numeric, or constant).`;
    return showing ? `${showing} ${dropped}` : dropped;
  }
  return showing;
}

// ---------------------------------------------------------------------------
// PNG export: serialize the card's SVG onto a canvas with title + legend.
// ---------------------------------------------------------------------------

const EXPORT_FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";

async function exportChartPng(
  host: HTMLElement,
  title: string,
  subtitle: string,
  legend: { label: string; color: string }[],
  t: ChartTheme,
): Promise<void> {
  const svg = host.querySelector("svg");
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  const width = Math.max(Math.round(rect.width), 320);
  const height = Math.max(Math.round(rect.height), 160);

  const cloned = svg.cloneNode(true) as SVGSVGElement;
  cloned.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  cloned.setAttribute("width", String(width));
  cloned.setAttribute("height", String(height));
  cloned.setAttribute("style", `font-family: ${EXPORT_FONT};`);
  const source = new XMLSerializer().serializeToString(cloned);
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`;

  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("Could not rasterize the chart SVG"));
    img.src = url;
  });

  const pad = 16;
  const titleBlock = 38; // title + subtitle
  const legendBlock = legend.length > 0 ? 22 : 0;
  const outW = width + pad * 2;
  const outH = height + titleBlock + legendBlock + pad * 2;
  const scale = 2; // crisp on hi-dpi screens

  const canvas = document.createElement("canvas");
  canvas.width = outW * scale;
  canvas.height = outH * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(scale, scale);

  ctx.fillStyle = t.surface;
  ctx.fillRect(0, 0, outW, outH);
  ctx.fillStyle = t.ink;
  ctx.font = `600 14px ${EXPORT_FONT}`;
  ctx.fillText(title, pad, pad + 12);
  ctx.fillStyle = t.axis;
  ctx.font = `11px ${EXPORT_FONT}`;
  ctx.fillText(subtitle, pad, pad + 28);
  ctx.drawImage(img, pad, pad + titleBlock, width, height);

  if (legend.length > 0) {
    let x = pad;
    const y = pad + titleBlock + height + 12;
    ctx.font = `11px ${EXPORT_FONT}`;
    for (const entry of legend) {
      // Measure BEFORE drawing so a long entry is skipped, not half-clipped.
      const entryWidth = 12 + ctx.measureText(entry.label).width + 14;
      if (x + entryWidth > outW - pad) break;
      ctx.fillStyle = entry.color;
      ctx.beginPath();
      ctx.arc(x + 4, y - 3, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = t.axis;
      ctx.fillText(entry.label, x + 12, y);
      x += entryWidth;
    }
  }

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${title.replace(/[\\/:*?"<>|]+/g, "_") || "chart"}.png`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function RunChartCard({ result }: { result: NodeResult }) {
  const t = useChartTheme();
  const hostRef = useRef<HTMLDivElement>(null);
  const art = result.chart;
  const subtitle = useMemo(() => (art ? artifactSubtitle(art) : ""), [art]);
  if (!art) return null;
  const note = truncationNote(art);
  // The user-set title (chart config) wins; the node label is the fallback.
  const title = art.title || result.label;

  return (
    <div className="border-b border-border px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold">{title}</div>
          <div className="truncate text-[11px] text-muted-foreground">
            {subtitle} · full run data
          </div>
        </div>
        <button
          onClick={() => {
            if (hostRef.current) {
              void exportChartPng(hostRef.current, title, subtitle, exportLegendEntries(art, t), t);
            }
          }}
          title="Download this chart as a PNG image"
          className="flex shrink-0 items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
        >
          <Download className="h-3.5 w-3.5" /> PNG
        </button>
      </div>
      <div ref={hostRef}>
        <RunChartView art={art} />
      </div>
      {note && <p className="mt-1 text-[10px] text-muted-foreground">{note}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Views: one per artifact kind
// ---------------------------------------------------------------------------

export function RunChartView({ art }: { art: ChartArtifact }) {
  switch (art.kind) {
    case "bar":
      return art.group_by ? <StackedBars art={art} /> : <CategoryBars art={art} />;
    case "histogram":
      return <HistogramBars art={art} />;
    case "line":
    case "area":
      return <LineArea art={art} />;
    case "scatter":
      return <ScatterDots art={art} />;
    case "pie":
      return <Donut art={art} />;
    case "boxplot":
      return <BoxPlotSvg art={art} />;
    case "heatmap":
      return <HeatmapSvg art={art} />;
    default:
      return <Placeholder>Unsupported chart artifact.</Placeholder>;
  }
}

function barName(art: ChartArtifact): string {
  if (art.aggregate === "count" || (!art.y && !art.value)) return "rows";
  return `${art.aggregate} of ${art.y ?? art.value}`;
}

function CategoryBars({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const data = art.data ?? [];
  if (data.length === 0) return <Placeholder>No data was recorded for this chart.</Placeholder>;
  const horizontal = art.orientation === "horizontal";
  const bar = (
    <Bar
      dataKey="value"
      name={barName(art)}
      fill={t.series[0]}
      maxBarSize={horizontal ? 18 : 24}
      radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
      isAnimationActive={false}
    >
      {data.map((d, i) => (
        <Cell key={i} fill={d.label === OTHER_LABEL ? t.neutral : t.series[0]} />
      ))}
    </Bar>
  );
  return (
    <ChartFrame>
      {horizontal ? (
        <BarChart data={data} layout="vertical">
          <CartesianGrid stroke={t.grid} horizontal={false} />
          <XAxis type="number" {...axisProps(t)} tickFormatter={fmtTick} />
          <YAxis
            type="category"
            dataKey="label"
            {...axisProps(t)}
            width={110}
            tickFormatter={(v: string) => {
              const s = fmtCategory(v);
              return s.length > 16 ? `${s.slice(0, 15)}…` : s;
            }}
          />
          <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
          {bar}
        </BarChart>
      ) : (
        <BarChart data={data}>
          <CartesianGrid {...gridProps(t)} />
          <XAxis dataKey="label" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
          <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
          <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
          {bar}
        </BarChart>
      )}
    </ChartFrame>
  );
}

function StackedBars({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const rows = art.rows ?? [];
  const series = art.series ?? [];
  if (rows.length === 0 || series.length === 0) {
    return <Placeholder>No data was recorded for this chart.</Placeholder>;
  }
  return (
    <ChartFrame>
      <BarChart data={rows}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="label" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
        <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
        <Legend {...legendProps(t)} />
        {series.map((s, i) => (
          <Bar
            key={s}
            dataKey={s}
            stackId="stack"
            fill={seriesColor(s, i, t)}
            // Surface-coloured stroke = the 2px gap between touching segments.
            stroke={t.surface}
            strokeWidth={1}
            maxBarSize={24}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ChartFrame>
  );
}

function HistogramBars({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const data = art.data ?? [];
  if (data.length === 0) return <Placeholder>No numeric values were recorded.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data} barCategoryGap={1}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="label" {...axisProps(t)} interval="preserveStartEnd" />
        <YAxis allowDecimals={false} {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip {...tooltipProps(t)} />
        <Bar dataKey="value" name="rows" fill={t.series[0]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ChartFrame>
  );
}

function LineArea({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const rows = art.rows ?? [];
  const series = art.series ?? [];
  if (rows.length === 0 || series.length === 0) {
    return <Placeholder>No data was recorded for this chart.</Placeholder>;
  }
  const area = art.kind === "area";
  const Chart = area ? AreaChart : LineChart;
  return (
    <ChartFrame>
      <Chart data={rows}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="x" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
        <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip
          {...tooltipProps(t)}
          cursor={{ stroke: t.grid }}
          formatter={fmtValue}
          labelFormatter={fmtCategory}
        />
        {series.length > 1 && <Legend {...legendProps(t)} />}
        {series.map((s, i) => {
          const color = seriesColor(s, i, t);
          const activeDot = { r: 4, fill: color, stroke: t.surface, strokeWidth: 2 };
          return area ? (
            <Area
              key={s}
              type="monotone"
              dataKey={s}
              stroke={color}
              strokeWidth={2}
              fill={color}
              fillOpacity={0.12}
              activeDot={activeDot}
              isAnimationActive={false}
            />
          ) : (
            <Line
              key={s}
              type="monotone"
              dataKey={s}
              stroke={color}
              strokeWidth={2}
              strokeLinecap="round"
              dot={false}
              activeDot={activeDot}
              isAnimationActive={false}
            />
          );
        })}
      </Chart>
    </ChartFrame>
  );
}

function ScatterDots({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const data = (art.points ?? [])
    .filter((p): p is [number, number] => p[0] !== null && p[1] !== null)
    .map(([x, y]) => ({ x, y }));
  if (data.length === 0) return <Placeholder>No numeric x/y pairs were recorded.</Placeholder>;
  return (
    <ChartFrame>
      <ScatterChart>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="x" name={art.x} type="number" {...axisProps(t)} tickFormatter={fmtTick} />
        <YAxis dataKey="y" name={art.y ?? "y"} type="number" {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <ZAxis range={[56, 56]} />
        <Tooltip {...tooltipProps(t)} cursor={{ stroke: t.grid }} formatter={fmtValue} />
        <Scatter data={data} fill={t.series[0]} stroke={t.surface} strokeWidth={1} isAnimationActive={false} />
      </ScatterChart>
    </ChartFrame>
  );
}

function Donut({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const data = (art.data ?? []).filter((d) => d.value !== null);
  if (data.length === 0) return <Placeholder>No data was recorded for this chart.</Placeholder>;
  return (
    <ChartFrame>
      <PieChart>
        <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
        <Legend {...legendProps(t)} />
        <Pie
          data={data}
          dataKey="value"
          nameKey="label"
          innerRadius="45%"
          outerRadius="80%"
          paddingAngle={2}
          stroke={t.surface}
          strokeWidth={2}
          isAnimationActive={false}
        >
          {data.map((d, i) => (
            <Cell key={i} fill={seriesColor(d.label, i, t)} />
          ))}
        </Pie>
      </PieChart>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Box plot — drawn as plain SVG (recharts has no box plot, and SVG keeps the
// PNG export path identical to every other chart on this screen).
// ---------------------------------------------------------------------------

const BOX_W = 480;
const BOX_H = 240;

function BoxPlotSvg({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  // Drop groups with any non-finite stat (the backend nulls NaN/inf): a null
  // would coerce to 0 in the scale math and draw the box in the wrong place.
  const groups = (art.groups ?? []).filter((g) =>
    [g.min, g.q1, g.median, g.q3, g.max].every((v) => typeof v === "number" && Number.isFinite(v)),
  );
  if (groups.length === 0) return <Placeholder>No numeric values were recorded.</Placeholder>;

  const lo = Math.min(...groups.map((g) => g.min));
  const hi = Math.max(...groups.map((g) => g.max));
  const span = hi - lo || 1;
  const pad = span * 0.06;
  const min = lo - pad;
  const max = hi + pad;

  const left = 46;
  const top = 8;
  const bottom = art.group_by ? 22 : 8;
  const plotW = BOX_W - left - 8;
  const plotH = BOX_H - top - bottom;
  const yFor = (v: number) => top + ((max - v) / (max - min)) * plotH;
  const ticks = [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4);
  const slotW = plotW / groups.length;

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${BOX_W} ${BOX_H}`} className="h-auto w-full" role="img">
        {ticks.map((v) => (
          <g key={v}>
            <line x1={left} x2={BOX_W - 8} y1={yFor(v)} y2={yFor(v)} stroke={t.grid} strokeWidth={1} />
            <text x={left - 4} y={yFor(v) + 3} textAnchor="end" fontSize={10} fill={t.axis}>
              {compact.format(v)}
            </text>
          </g>
        ))}
        {groups.map((g, i) => (
          <BoxMarkSvg key={g.label} g={g} cx={left + slotW * (i + 0.5)} yFor={yFor} t={t} showLabel={!!art.group_by} labelY={BOX_H - 6} />
        ))}
      </svg>
    </div>
  );
}

function BoxMarkSvg({
  g,
  cx,
  yFor,
  t,
  showLabel,
  labelY,
}: {
  g: BoxGroupStats;
  cx: number;
  yFor: (v: number) => number;
  t: ChartTheme;
  showLabel: boolean;
  labelY: number;
}) {
  const color = t.series[0];
  const boxW = 28;
  const title = [
    g.label,
    `max (in fence): ${full.format(g.max)}`,
    `q3: ${full.format(g.q3)}`,
    `median: ${full.format(g.median)}`,
    `q1: ${full.format(g.q1)}`,
    `min (in fence): ${full.format(g.min)}`,
    `n = ${g.count}${g.outliers > 0 ? ` (${g.outliers} outlier${g.outliers === 1 ? "" : "s"} not drawn)` : ""}`,
  ].join("\n");
  const label = g.label.length > 10 ? `${g.label.slice(0, 9)}…` : g.label;
  return (
    <g>
      <title>{title}</title>
      <line x1={cx} x2={cx} y1={yFor(g.max)} y2={yFor(g.min)} stroke={color} strokeWidth={1} />
      {[g.max, g.min].map((v) => (
        <line key={v} x1={cx - 6} x2={cx + 6} y1={yFor(v)} y2={yFor(v)} stroke={color} strokeWidth={1} />
      ))}
      <rect
        x={cx - boxW / 2}
        y={yFor(g.q3)}
        width={boxW}
        height={Math.max(yFor(g.q1) - yFor(g.q3), 1)}
        rx={3}
        fill={`${color}2e`}
        stroke={color}
        strokeWidth={1.5}
      />
      <line x1={cx - boxW / 2} x2={cx + boxW / 2} y1={yFor(g.median)} y2={yFor(g.median)} stroke={color} strokeWidth={2} />
      {showLabel && (
        <text x={cx} y={labelY} textAnchor="middle" fontSize={10} fill={t.axis}>
          {label}
        </text>
      )}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Correlation heatmap — plain SVG grid for the same export-friendliness.
// ---------------------------------------------------------------------------

function HeatmapSvg({ art }: { art: ChartArtifact }) {
  const t = useChartTheme();
  const cols = art.columns ?? [];
  const matrix = art.matrix ?? [];
  if (cols.length < 2 || matrix.length === 0) {
    return <Placeholder>Not enough numeric columns were recorded.</Placeholder>;
  }
  const cell = 40;
  const gap = 2;
  const labelW = 76;
  const labelH = 18;
  const w = labelW + cols.length * (cell + gap);
  const h = labelH + cols.length * (20 + gap);
  const cellH = 20;
  const fillFor = (v: number) =>
    mixHex(t.divergingMid, v >= 0 ? t.divergingPos : t.divergingNeg, Math.abs(clamp(v, -1, 1)));
  const short = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img">
        {cols.map((c, j) => (
          <text
            key={c}
            x={labelW + j * (cell + gap) + cell / 2}
            y={labelH - 6}
            textAnchor="middle"
            fontSize={9}
            fill={t.axis}
          >
            {short(c, 9)}
          </text>
        ))}
        {cols.map((rowCol, i) => (
          <g key={rowCol}>
            <text
              x={labelW - 6}
              y={labelH + i * (cellH + gap) + cellH / 2 + 3}
              textAnchor="end"
              fontSize={9}
              fill={t.axis}
            >
              {short(rowCol, 12)}
            </text>
            {cols.map((colCol, j) => {
              const v = matrix[i]?.[j] ?? null;
              const fill = v === null ? t.cursor : fillFor(v);
              return (
                <g key={colCol}>
                  <title>{`${rowCol} × ${colCol}: ${v === null ? "n/a" : v.toFixed(2)}`}</title>
                  <rect
                    x={labelW + j * (cell + gap)}
                    y={labelH + i * (cellH + gap)}
                    width={cell}
                    height={cellH}
                    rx={2}
                    fill={fill}
                  />
                  <text
                    x={labelW + j * (cell + gap) + cell / 2}
                    y={labelH + i * (cellH + gap) + cellH / 2 + 3}
                    textAnchor="middle"
                    fontSize={9}
                    fill={v === null ? t.axis : inkForFill(fill)}
                  >
                    {v === null ? "–" : v.toFixed(2)}
                  </text>
                </g>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}
