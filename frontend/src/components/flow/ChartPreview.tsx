// Renders a chart for the selected node from its preview sample rows. Charts are
// derived entirely client-side from the preview sample — the backend never
// computes them — so they reflect a sample of the data, not the full dataset.
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
  correlationColor,
  correlationMatrix,
  histogram,
  numericColumns,
  toNumber,
  valueCounts,
  type Aggregate,
  type BarDatum,
  type Row,
} from "@/lib/chartData";

interface ChartPreviewProps {
  type: string;
  config: Record<string, unknown>;
  /** Sample rows from the node directly upstream of this viz node. */
  rows: Row[] | null;
}

// A small palette for multi-series line charts.
const SERIES_COLORS = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#06b6d4"];

export function ChartPreview({ type, config, rows }: ChartPreviewProps) {
  if (!rows || rows.length === 0) {
    return <Placeholder>Run a preview to see the chart.</Placeholder>;
  }

  switch (type) {
    case "histogramChart":
      return <HistogramView rows={rows} config={config} />;
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
    case "valueCounts":
      return <ValueCountsView rows={rows} config={config} />;
    case "pieChart":
      return <PieView rows={rows} config={config} />;
    default:
      return <Placeholder>Unsupported chart type.</Placeholder>;
  }
}

function HistogramView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const column = typeof config.column === "string" ? config.column : "";
  const bins = typeof config.bins === "number" ? config.bins : 20;
  if (!column) return <Placeholder>Pick a column to chart.</Placeholder>;
  const data = histogram(rows, column, bins);
  if (data.length === 0) return <Placeholder>No numeric values in “{column}”.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="count" fill="#6366f1" />
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
  const x = typeof config.x === "string" ? config.x : "";
  const ys = Array.isArray(config.y) ? (config.y.filter((v) => typeof v === "string") as string[]) : [];
  if (!x || ys.length === 0) return <Placeholder>Pick an x axis and at least one series.</Placeholder>;
  const data = rows.map((r) => {
    const point: Record<string, unknown> = { [x]: r[x] };
    for (const y of ys) point[y] = toNumber(r[y]);
    return point;
  });
  const Chart = area ? AreaChart : LineChart;
  return (
    <ChartFrame>
      <Chart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey={x} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        {ys.map((y, i) => {
          const color = SERIES_COLORS[i % SERIES_COLORS.length];
          return area ? (
            <Area
              key={y}
              type="monotone"
              dataKey={y}
              stroke={color}
              fill={color}
              fillOpacity={0.25}
              isAnimationActive={false}
            />
          ) : (
            <Line
              key={y}
              type="monotone"
              dataKey={y}
              stroke={color}
              dot={false}
              isAnimationActive={false}
            />
          );
        })}
      </Chart>
    </ChartFrame>
  );
}

function ScatterView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
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
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="x" name={x} type="number" tick={{ fontSize: 10 }} />
        <YAxis dataKey="y" name={y} type="number" tick={{ fontSize: 10 }} />
        <ZAxis range={[40, 40]} />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
        <Scatter data={data} fill="#6366f1" isAnimationActive={false} />
      </ScatterChart>
    </ChartFrame>
  );
}

function BarView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  const aggregate = (typeof config.aggregate === "string" ? config.aggregate : "sum") as Aggregate;
  if (!x || !y) return <Placeholder>Pick a category and a value column.</Placeholder>;
  const data = barData(rows, x, y, aggregate);
  return (
    <ChartFrame>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="category" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="value" fill="#ec4899" />
      </BarChart>
    </ChartFrame>
  );
}

function ValueCountsView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const column = typeof config.column === "string" ? config.column : "";
  if (!column) return <Placeholder>Pick a column to count.</Placeholder>;
  const data = topN(valueCounts(rows, column), 20);
  if (data.length === 0) return <Placeholder>No values to count.</Placeholder>;
  return (
    <ChartFrame>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="category" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="value" fill="#8b5cf6" />
      </BarChart>
    </ChartFrame>
  );
}

function PieView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const x = typeof config.x === "string" ? config.x : "";
  const y = typeof config.y === "string" ? config.y : "";
  const aggregate = (typeof config.aggregate === "string" ? config.aggregate : "sum") as Aggregate;
  if (!x || !y) return <Placeholder>Pick a category and a value column.</Placeholder>;
  const data = topN(barData(rows, x, y, aggregate), 12);
  if (data.length === 0) return <Placeholder>No values to chart.</Placeholder>;
  return (
    <ChartFrame>
      <PieChart>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        <Pie data={data} dataKey="value" nameKey="category" outerRadius="75%" isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
          ))}
        </Pie>
      </PieChart>
    </ChartFrame>
  );
}

/** Keep the largest-N categories by value so dense charts stay readable. */
function topN(data: BarDatum[], n: number): BarDatum[] {
  return [...data].sort((a, b) => b.value - a.value).slice(0, n);
}

function HeatmapView({ rows, config }: { rows: Row[]; config: Record<string, unknown> }) {
  const picked = Array.isArray(config.columns)
    ? (config.columns.filter((v) => typeof v === "string") as string[])
    : [];
  const allCols = Object.keys(rows[0] ?? {});
  const cols = (picked.length ? picked : numericColumns(rows, allCols)).filter((c) =>
    allCols.includes(c),
  );
  if (cols.length < 2) {
    return <Placeholder>Need at least two numeric columns for a correlation heatmap.</Placeholder>;
  }
  const { matrix } = correlationMatrix(rows, cols);
  return (
    <div className="overflow-auto p-1">
      <table className="border-collapse text-[10px]">
        <thead>
          <tr>
            <th className="p-1" />
            {cols.map((c) => (
              <th key={c} className="max-w-[64px] truncate p-1 text-left font-medium text-slate-500">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cols.map((rowCol, i) => (
            <tr key={rowCol}>
              <td className="max-w-[64px] truncate p-1 font-medium text-slate-500">{rowCol}</td>
              {cols.map((colCol, j) => {
                const v = matrix[i][j];
                return (
                  <td
                    key={colCol}
                    title={`${rowCol} × ${colCol}: ${v.toFixed(2)}`}
                    className="p-1 text-center text-slate-700"
                    style={{ backgroundColor: correlationColor(v), minWidth: 36 }}
                  >
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
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
