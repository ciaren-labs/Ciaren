// Renders a chart for the selected node from its preview sample rows. Charts are
// derived entirely client-side from the preview sample — the backend never
// computes them — so they reflect a sample of the data, not the full dataset.
//
// Styling follows the app's dataviz conventions: theme-aware tokens from
// chartTheme.ts (validated palettes for both modes), solid hairline gridlines,
// thin rounded-end bars, surface-coloured gaps between touching marks, and
// legends only when there are two or more series.
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
import { ResponsiveContainer } from "recharts";
import {
  barData,
  boxplotStats,
  clamp,
  correlationMatrix,
  histogram,
  numericColumns,
  sortByX,
  stackedBarData,
  toNumber,
  topN,
  topNWithOther,
  valueCounts,
  type Aggregate,
  type BoxStats,
  type Row,
} from "@/lib/chartData";
import { inkForFill, mixHex, useChartTheme, type ChartTheme } from "@/lib/chartTheme";

interface ChartPreviewProps {
  type: string;
  config: Record<string, unknown>;
  /** Sample rows from the node directly upstream of this viz node. */
  rows: Row[] | null;
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

function fmtTick(v: unknown): string {
  const n = toNumber(v);
  return n === null ? String(v ?? "") : compact.format(n);
}

function fmtValue(v: unknown): string {
  const n = toNumber(v);
  return n === null ? String(v ?? "") : full.format(n);
}

/** Trim ISO datetime axis labels: "2023-01-08T00:00:00.000" → "2023-01-08". */
function fmtCategory(v: unknown): string {
  const s = String(v ?? "");
  const iso = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(s);
  if (!iso) return s;
  return iso[2] === "00:00" ? iso[1] : `${iso[1]} ${iso[2]}`;
}

export function ChartPreview({ type, config, rows }: ChartPreviewProps) {
  if (!rows || rows.length === 0) {
    return <Placeholder>Run a preview to see the chart.</Placeholder>;
  }

  switch (type) {
    case "histogramChart":
      return <HistogramView rows={rows} config={config} />;
    case "boxPlot":
      return <BoxPlotView rows={rows} config={config} />;
    case "correlationHeatmap":
      return <HeatmapView rows={rows} config={config} />;
    case "lineChart":
      return <LineView rows={rows} config={config} />;
    case "areaChart":
      return <LineView rows={rows} config={config} area />;
    case "scatterChart":
      return <ScatterView rows={rows} config={config} />;
    case "barChart":
      return <BarView rows={rows} config={config} />;
    case "horizontalBarChart":
      return <BarView rows={rows} config={config} horizontal />;
    case "stackedBarChart":
      return <StackedBarView rows={rows} config={config} />;
    case "valueCounts":
      return <ValueCountsView rows={rows} config={config} />;
    case "pieChart":
      return <PieView rows={rows} config={config} />;
    default:
      return <Placeholder>Unsupported chart type.</Placeholder>;
  }
}

// -- Shared chrome ---------------------------------------------------------

/** Recessive axis: muted tick text, hairline axis rule, no tick marks. */
function axisProps(t: ChartTheme) {
  return {
    tick: { fontSize: 10, fill: t.axis },
    axisLine: { stroke: t.grid },
    tickLine: false as const,
  };
}

function gridProps(t: ChartTheme) {
  // Solid hairlines, horizontal only — the grid must stay recessive.
  return { vertical: false, stroke: t.grid };
}

function tooltipProps(t: ChartTheme) {
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

function legendProps(t: ChartTheme) {
  return {
    iconType: "circle" as const,
    iconSize: 8,
    // Legend text wears ink, not the series colour — the swatch carries identity.
    formatter: (value: string) => <span style={{ color: t.axis, fontSize: 11 }}>{value}</span>,
  };
}

// -- Views -------------------------------------------------------------------

function HistogramView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const column = typeof config.column === "string" ? config.column : "";
  const bins = typeof config.bins === "number" ? config.bins : 20;
  if (!column) return <Placeholder>Pick a column to chart.</Placeholder>;
  const data = histogram(rows, column, clamp(bins, 1, 100));
  if (data.length === 0) return <Placeholder>No numeric values in “{column}”.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data} barCategoryGap={1}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="label" {...axisProps(t)} interval="preserveStartEnd" />
        <YAxis allowDecimals={false} {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip {...tooltipProps(t)} />
        <Bar dataKey="count" name="rows" fill={t.series[0]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ChartFrame>
  );
}

function LineView({
  rows,
  config,
  area = false,
}: {
  rows: Row[];
  config: Record<string, unknown>;
  area?: boolean;
}) {
  const t = useChartTheme();
  const x = typeof config.x === "string" ? config.x : "";
  const ys = Array.isArray(config.y) ? (config.y.filter((v) => typeof v === "string") as string[]) : [];
  if (!x || ys.length === 0) return <Placeholder>Pick an x axis and at least one series.</Placeholder>;
  // Sort by x when it has a natural order so the line doesn't scribble.
  const data = sortByX(rows, x).map((r) => {
    const point: Record<string, unknown> = { [x]: r[x] };
    for (const y of ys) point[y] = toNumber(r[y]);
    return point;
  });
  const Chart = area ? AreaChart : LineChart;
  return (
    <ChartFrame>
      <Chart data={data}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey={x} {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
        <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip
          {...tooltipProps(t)}
          cursor={{ stroke: t.grid }}
          formatter={fmtValue}
          labelFormatter={fmtCategory}
        />
        {ys.length > 1 && <Legend {...legendProps(t)} />}
        {ys.map((y, i) => {
          const color = t.series[i % t.series.length];
          const activeDot = { r: 4, fill: color, stroke: t.surface, strokeWidth: 2 };
          return area ? (
            <Area
              key={y}
              type="monotone"
              dataKey={y}
              stroke={color}
              strokeWidth={2}
              fill={color}
              fillOpacity={0.12}
              activeDot={activeDot}
              isAnimationActive={false}
            />
          ) : (
            <Line
              key={y}
              type="monotone"
              dataKey={y}
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

function ScatterView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  if (!x || !y) return <Placeholder>Pick an x and a y column.</Placeholder>;
  const data = rows
    .map((r) => ({ x: toNumber(r[x]), y: toNumber(r[y]) }))
    .filter((p): p is { x: number; y: number } => p.x !== null && p.y !== null);
  if (data.length === 0) return <Placeholder>No numeric x/y pairs to plot.</Placeholder>;
  return (
    <ChartFrame>
      <ScatterChart>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="x" name={x} type="number" {...axisProps(t)} tickFormatter={fmtTick} />
        <YAxis dataKey="y" name={y} type="number" {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <ZAxis range={[56, 56]} />
        <Tooltip {...tooltipProps(t)} cursor={{ stroke: t.grid }} formatter={fmtValue} />
        {/* Surface ring keeps overlapping dots legible. */}
        <Scatter data={data} fill={t.series[0]} stroke={t.surface} strokeWidth={1} isAnimationActive={false} />
      </ScatterChart>
    </ChartFrame>
  );
}

function BarView({
  rows,
  config,
  horizontal = false,
}: {
  rows: Row[];
  config: Record<string, unknown>;
  horizontal?: boolean;
}) {
  const t = useChartTheme();
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  const aggregate = (typeof config.aggregate === "string" ? config.aggregate : "sum") as Aggregate;
  if (!x || !y) return <Placeholder>Pick a category and a value column.</Placeholder>;
  const data = topN(barData(rows, x, y, aggregate), horizontal ? 15 : 25);
  if (data.length === 0) return <Placeholder>No data to chart.</Placeholder>;
  const name = aggregate === "count" ? "rows" : `${aggregate} of ${y}`;
  const bar = (
    <Bar
      dataKey="value"
      name={name}
      fill={t.series[0]}
      maxBarSize={horizontal ? 18 : 24}
      radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
      isAnimationActive={false}
    />
  );
  return (
    <ChartFrame>
      {horizontal ? (
        <BarChart data={data} layout="vertical">
          <CartesianGrid stroke={t.grid} horizontal={false} />
          <XAxis type="number" {...axisProps(t)} tickFormatter={fmtTick} />
          <YAxis
            type="category"
            dataKey="category"
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
          <XAxis dataKey="category" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
          <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
          <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
          {bar}
        </BarChart>
      )}
    </ChartFrame>
  );
}

function StackedBarView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  const group = typeof config.group === "string" ? config.group : "";
  const aggregate = (typeof config.aggregate === "string" ? config.aggregate : "sum") as Aggregate;
  if (!x || !y || !group) return <Placeholder>Pick a category, value, and group-by column.</Placeholder>;
  const { data, groups } = stackedBarData(rows, x, y, group, aggregate);
  if (data.length === 0) return <Placeholder>No data to chart.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="category" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
        <YAxis {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
        <Legend {...legendProps(t)} />
        {groups.map((g, i) => (
          <Bar
            key={g}
            dataKey={g}
            stackId="stack"
            fill={t.series[i % t.series.length]}
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

function ValueCountsView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const column = typeof config.column === "string" ? config.column : "";
  if (!column) return <Placeholder>Pick a column to count.</Placeholder>;
  const data = topN(valueCounts(rows, column), 20);
  if (data.length === 0) return <Placeholder>No values to count.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data}>
        <CartesianGrid {...gridProps(t)} />
        <XAxis dataKey="category" {...axisProps(t)} interval="preserveStartEnd" tickFormatter={fmtCategory} />
        <YAxis allowDecimals={false} {...axisProps(t)} tickFormatter={fmtTick} width={40} />
        <Tooltip {...tooltipProps(t)} />
        <Bar
          dataKey="value"
          name="rows"
          fill={t.series[0]}
          maxBarSize={24}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartFrame>
  );
}

function PieView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  const aggregate = (typeof config.aggregate === "string" ? config.aggregate : "sum") as Aggregate;
  if (!x || !y) return <Placeholder>Pick a category and a value column.</Placeholder>;
  // Part-to-whole stays readable up to ~6 segments; the tail folds into "Other".
  const data = topNWithOther(barData(rows, x, y, aggregate), 6);
  if (data.length === 0) return <Placeholder>No values to chart.</Placeholder>;
  return (
    <ChartFrame>
      <PieChart>
        <Tooltip {...tooltipProps(t)} formatter={fmtValue} />
        <Legend {...legendProps(t)} />
        <Pie
          data={data}
          dataKey="value"
          nameKey="category"
          innerRadius="45%"
          outerRadius="80%"
          paddingAngle={2}
          stroke={t.surface}
          strokeWidth={2}
          isAnimationActive={false}
        >
          {data.map((d, i) => (
            <Cell key={i} fill={d.category === "Other" ? t.neutral : t.series[i % t.series.length]} />
          ))}
        </Pie>
      </PieChart>
    </ChartFrame>
  );
}

/**
 * Box-and-whisker plot rendered with plain positioned divs (recharts has no
 * boxplot). Whiskers span the extremes inside the 1.5·IQR Tukey fences;
 * outliers are reported in the tooltip rather than drawn.
 */
function BoxPlotView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const y = typeof config.y === "string" ? config.y : "";
  const by = typeof config.group === "string" && config.group !== "" ? config.group : null;
  if (!y) return <Placeholder>Pick a numeric value column.</Placeholder>;
  const stats = boxplotStats(rows, y, by);
  if (stats.length === 0) return <Placeholder>No numeric values in “{y}”.</Placeholder>;

  const lo = Math.min(...stats.map((s) => s.lo));
  const hi = Math.max(...stats.map((s) => s.hi));
  const span = hi - lo || 1;
  const pad = span * 0.06;
  const min = lo - pad;
  const max = hi + pad;
  /** Percent from the top of the plot area for a data value. */
  const pos = (v: number) => ((max - v) / (max - min)) * 100;
  const ticks = [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4);

  return (
    <div className="h-56 w-full">
      <div className="flex h-[calc(100%-1.25rem)]">
        {/* Y axis tick labels */}
        <div className="relative w-10 shrink-0">
          {ticks.map((v) => (
            <span
              key={v}
              className="absolute right-1 -translate-y-1/2 text-[10px]"
              style={{ top: `${pos(v)}%`, color: t.axis }}
            >
              {compact.format(v)}
            </span>
          ))}
        </div>
        {/* Plot area */}
        <div className="relative flex-1">
          {ticks.map((v) => (
            <div
              key={v}
              className="absolute inset-x-0"
              style={{ top: `${pos(v)}%`, borderTop: `1px solid ${t.grid}` }}
            />
          ))}
          <div className="absolute inset-0 flex">
            {stats.map((s) => (
              <BoxMark key={s.category} stats={s} pos={pos} t={t} />
            ))}
          </div>
        </div>
      </div>
      {/* Category labels */}
      <div className="flex h-5 pl-10">
        {stats.map((s) => (
          <span
            key={s.category}
            className="min-w-0 flex-1 truncate px-0.5 text-center text-[10px]"
            style={{ color: t.axis }}
            title={s.category}
          >
            {by ? s.category : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function BoxMark({
  stats: s,
  pos,
  t,
}: {
  stats: BoxStats;
  pos: (v: number) => number;
  t: ChartTheme;
}) {
  const color = t.series[0];
  const title = [
    s.category,
    `max (in fence): ${full.format(s.hi)}`,
    `q3: ${full.format(s.q3)}`,
    `median: ${full.format(s.median)}`,
    `q1: ${full.format(s.q1)}`,
    `min (in fence): ${full.format(s.lo)}`,
    `n = ${s.count}${s.outliers > 0 ? ` (${s.outliers} outlier${s.outliers === 1 ? "" : "s"} not drawn)` : ""}`,
  ].join("\n");
  return (
    <div className="relative min-w-0 flex-1" title={title}>
      {/* Whisker */}
      <div
        className="absolute left-1/2 w-px -translate-x-1/2"
        style={{ top: `${pos(s.hi)}%`, height: `${pos(s.lo) - pos(s.hi)}%`, backgroundColor: color }}
      />
      {/* Whisker caps */}
      {[s.hi, s.lo].map((v) => (
        <div
          key={v}
          className="absolute left-1/2 h-px w-3 -translate-x-1/2"
          style={{ top: `${pos(v)}%`, backgroundColor: color }}
        />
      ))}
      {/* IQR box */}
      <div
        className="absolute left-1/2 w-3/5 max-w-[36px] -translate-x-1/2 rounded-[3px]"
        style={{
          top: `${pos(s.q3)}%`,
          height: `${Math.max(pos(s.q1) - pos(s.q3), 0.5)}%`,
          backgroundColor: `${color}2e`,
          border: `1.5px solid ${color}`,
        }}
      />
      {/* Median */}
      <div
        className="absolute left-1/2 h-0.5 w-3/5 max-w-[36px] -translate-x-1/2"
        style={{ top: `${pos(s.median)}%`, backgroundColor: color }}
      />
    </div>
  );
}

// Beyond this many columns the correlation table stops being readable.
const HEATMAP_MAX_COLUMNS = 12;

function HeatmapView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const t = useChartTheme();
  const picked = Array.isArray(config.columns)
    ? (config.columns.filter((v) => typeof v === "string") as string[])
    : [];
  const allCols = Object.keys(rows[0] ?? {});
  const candidates = (picked.length ? picked : numericColumns(rows, allCols)).filter((c) =>
    allCols.includes(c),
  );
  const cols = candidates.slice(0, HEATMAP_MAX_COLUMNS);
  if (cols.length < 2) {
    return <Placeholder>Need at least two numeric columns for a correlation heatmap.</Placeholder>;
  }
  const { matrix } = correlationMatrix(rows, cols);
  const fillFor = (v: number) =>
    mixHex(t.divergingMid, v >= 0 ? t.divergingPos : t.divergingNeg, Math.abs(clamp(v, -1, 1)));
  return (
    <div className="overflow-auto p-1">
      <table className="border-separate text-[10px]" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="p-1" />
            {cols.map((c) => (
              <th
                key={c}
                className="max-w-[64px] truncate p-1 text-left font-medium"
                style={{ color: t.axis }}
                title={c}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cols.map((rowCol, i) => (
            <tr key={rowCol}>
              <td
                className="max-w-[64px] truncate p-1 font-medium"
                style={{ color: t.axis }}
                title={rowCol}
              >
                {rowCol}
              </td>
              {cols.map((colCol, j) => {
                const v = matrix[i][j];
                const fill = fillFor(v);
                return (
                  <td
                    key={colCol}
                    title={`${rowCol} × ${colCol}: ${v.toFixed(2)}`}
                    className="rounded-sm p-1 text-center"
                    style={{ backgroundColor: fill, color: inkForFill(fill), minWidth: 36 }}
                  >
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {candidates.length > cols.length && (
        <p className="mt-1 text-[10px]" style={{ color: t.axis }}>
          Showing the first {cols.length} of {candidates.length} numeric columns.
        </p>
      )}
    </div>
  );
}

function ChartFrame({ children }: { children: React.ReactElement }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border bg-muted/40 p-4 text-center text-xs text-muted-foreground">
      {children}
    </div>
  );
}
