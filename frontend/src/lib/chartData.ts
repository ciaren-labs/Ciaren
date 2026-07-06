// Pure data helpers for the visualization (chart) nodes. They turn an array of
// preview row objects + a node config into the small derived structures the
// recharts components consume. Kept dependency-free so they can be unit-tested.

export type Row = Record<string, unknown>;

/** Coerce an arbitrary cell to a finite number, or null when it isn't numeric. */
export function toNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value ? 1 : 0;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * Columns whose values are (mostly) numeric across the sample. A column counts
 * as numeric when at least half of its non-null cells parse as numbers.
 */
export function numericColumns(rows: Row[], columns: string[]): string[] {
  return columns.filter((col) => {
    let nonNull = 0;
    let numeric = 0;
    for (const row of rows) {
      const v = row[col];
      if (v === null || v === undefined || v === "") continue;
      nonNull += 1;
      if (toNumber(v) !== null) numeric += 1;
    }
    return nonNull > 0 && numeric / nonNull >= 0.5;
  });
}

export interface HistogramBin {
  /** Human-readable bucket range label, e.g. "1.0–2.5". */
  label: string;
  /** Bucket lower bound (inclusive). */
  start: number;
  /** Bucket upper bound (exclusive, except the last bin). */
  end: number;
  count: number;
}

/** Build equal-width histogram buckets for a numeric column. */
export function histogram(rows: Row[], column: string, bins: number): HistogramBin[] {
  const values = rows
    .map((r) => toNumber(r[column]))
    .filter((v): v is number => v !== null);
  const binCount = Math.max(1, Math.floor(bins) || 1);
  if (values.length === 0) return [];

  const min = Math.min(...values);
  const max = Math.max(...values);
  // A constant column collapses to a single bucket.
  if (min === max) {
    return [{ label: format(min), start: min, end: max, count: values.length }];
  }

  const width = (max - min) / binCount;
  const result: HistogramBin[] = Array.from({ length: binCount }, (_, i) => {
    const start = min + i * width;
    const end = i === binCount - 1 ? max : start + width;
    return { label: `${format(start)}–${format(end)}`, start, end, count: 0 };
  });
  for (const v of values) {
    let idx = Math.floor((v - min) / width);
    if (idx >= binCount) idx = binCount - 1; // the max lands in the last bin
    if (idx < 0) idx = 0;
    result[idx].count += 1;
  }
  return result;
}

/**
 * Pearson correlation matrix over the given numeric columns. Returns a square
 * matrix aligned with `columns`; pairs with no shared finite values are 0.
 */
export function correlationMatrix(
  rows: Row[],
  columns: string[],
): { columns: string[]; matrix: number[][] } {
  const series = columns.map((col) => rows.map((r) => toNumber(r[col])));
  const n = columns.length;
  const matrix: number[][] = Array.from({ length: n }, () => Array<number>(n).fill(0));
  for (let i = 0; i < n; i += 1) {
    for (let j = i; j < n; j += 1) {
      const r = pearson(series[i], series[j]);
      matrix[i][j] = r;
      matrix[j][i] = r;
    }
  }
  return { columns, matrix };
}

/** Pearson correlation over paired arrays, skipping positions where either is null. */
export function pearson(a: (number | null)[], b: (number | null)[]): number {
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
    if (a[i] === null || b[i] === null) continue;
    xs.push(a[i] as number);
    ys.push(b[i] as number);
  }
  const len = xs.length;
  if (len < 2) return i_equals(xs, ys) ? 1 : 0;

  const mean = (arr: number[]) => arr.reduce((s, v) => s + v, 0) / arr.length;
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < len; i += 1) {
    const vx = xs[i] - mx;
    const vy = ys[i] - my;
    num += vx * vy;
    dx += vx * vx;
    dy += vy * vy;
  }
  const denom = Math.sqrt(dx * dy);
  if (denom === 0) return 0; // a constant series has no linear correlation
  return clamp(num / denom, -1, 1);
}

export type Aggregate = "sum" | "mean" | "count" | "min" | "max";

export interface BarDatum {
  category: string;
  value: number;
}

/** Roll a value column up by a category column using the chosen aggregate. */
export function barData(
  rows: Row[],
  x: string,
  y: string,
  aggregate: Aggregate,
): BarDatum[] {
  const groups = new Map<string, { values: number[]; rows: number }>();
  for (const row of rows) {
    const key = blankLabel(row[x]);
    const v = toNumber(row[y]);
    const group = groups.get(key) ?? { values: [], rows: 0 };
    group.rows += 1;
    if (v !== null) group.values.push(v);
    groups.set(key, group);
  }
  return [...groups.entries()].map(([category, group]) => ({
    category,
    // "count" means "how many rows", not "how many numeric cells" — a text-only
    // value column must still produce counts.
    value: aggregate === "count" ? group.rows : aggregateValues(group.values, aggregate),
  }));
}

function blankLabel(cell: unknown): string {
  return cell === null || cell === undefined || cell === "" ? "(blank)" : String(cell);
}

/** Keep the largest-N categories by value so dense charts stay readable. */
export function topN(data: BarDatum[], n: number): BarDatum[] {
  return [...data].sort((a, b) => b.value - a.value).slice(0, n);
}

/**
 * Keep the largest-N categories and fold the tail into a single "Other" bucket,
 * so part-to-whole charts never explode past a readable segment count.
 */
export function topNWithOther(data: BarDatum[], n: number): BarDatum[] {
  if (data.length <= n) return topN(data, n);
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const head = sorted.slice(0, n - 1);
  const other = sorted.slice(n - 1).reduce((s, d) => s + d.value, 0);
  return [...head, { category: "Other", value: other }];
}

/** Columns that are NOT numeric — good defaults for category / x-axis picks. */
export function categoricalColumns(rows: Row[], columns: string[]): string[] {
  const numeric = new Set(numericColumns(rows, columns));
  return columns.filter((c) => !numeric.has(c));
}

/** Count how many rows fall into each distinct value of a column (frequency). */
export function valueCounts(rows: Row[], column: string): BarDatum[] {
  const groups = new Map<string, number>();
  for (const row of rows) {
    const key = blankLabel(row[column]);
    groups.set(key, (groups.get(key) ?? 0) + 1);
  }
  return [...groups.entries()].map(([category, value]) => ({ category, value }));
}

/**
 * Columns whose values are (mostly) dates across the sample: Date instances or
 * date-shaped strings (ISO "2024-01-31", "2024-01-31T…", "31/01/2024"). Plain
 * numbers are never dates — `Date.parse("2020")` succeeding must not turn a
 * numeric year column into a datetime axis.
 */
export function datetimeColumns(rows: Row[], columns: string[]): string[] {
  return columns.filter((col) => {
    let nonNull = 0;
    let dateLike = 0;
    for (const row of rows) {
      const v = row[col];
      if (v === null || v === undefined || v === "") continue;
      nonNull += 1;
      if (isDateLike(v)) dateLike += 1;
    }
    return nonNull > 0 && dateLike / nonNull >= 0.8;
  });
}

const ISO_SHAPE = /^\d{4}-\d{2}-\d{2}([T ].*)?$/; // ISO date / datetime
const DMY_SHAPE = /^(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}$/; // 31/01/2024, 1.2.24

function isDateLike(value: unknown): boolean {
  if (value instanceof Date) return !Number.isNaN(value.getTime());
  if (typeof value !== "string") return false;
  const s = value.trim();
  if (ISO_SHAPE.test(s)) return !Number.isNaN(Date.parse(s));
  // Date.parse can't be trusted for day-first strings ("31/01/2024" is NaN in
  // V8), so accept the shape when the two leading parts can be a day + month.
  const dmy = DMY_SHAPE.exec(s);
  if (!dmy) return false;
  const a = Number(dmy[1]);
  const b = Number(dmy[2]);
  return (a >= 1 && a <= 31 && b >= 1 && b <= 12) || (a >= 1 && a <= 12 && b >= 1 && b <= 31);
}

/** Distinct-value count per column — the basis for "good default" picks. */
export function columnCardinalities(rows: Row[], columns: string[]): Map<string, number> {
  const sets = new Map<string, Set<string>>(columns.map((c) => [c, new Set<string>()]));
  for (const row of rows) {
    for (const col of columns) {
      sets.get(col)!.add(blankLabel(row[col]));
    }
  }
  return new Map(columns.map((c) => [c, sets.get(c)!.size]));
}

/**
 * Sort rows by the x column when it has a natural order (dates or numbers), so
 * line/area charts don't scribble back and forth on unsorted samples. Text x
 * values keep the incoming row order.
 */
export function sortByX(rows: Row[], x: string): Row[] {
  const values = rows.map((r) => r[x]).filter((v) => v !== null && v !== undefined && v !== "");
  if (values.length === 0) return rows;
  if (values.every((v) => toNumber(v) !== null)) {
    return [...rows].sort((a, b) => (toNumber(a[x]) ?? 0) - (toNumber(b[x]) ?? 0));
  }
  if (values.every((v) => isDateLike(v))) {
    const time = (v: unknown) =>
      v instanceof Date ? v.getTime() : Date.parse(String(v));
    return [...rows].sort((a, b) => (time(a[x]) || 0) - (time(b[x]) || 0));
  }
  return rows;
}

export interface BoxStats {
  category: string;
  /** Whisker ends: extreme values inside the 1.5·IQR Tukey fences. */
  lo: number;
  q1: number;
  median: number;
  q3: number;
  hi: number;
  /** Number of numeric values behind the box. */
  count: number;
  /** Values outside the fences (not drawn, surfaced in the tooltip). */
  outliers: number;
}

/**
 * Five-number summaries of a numeric column, optionally grouped by a category
 * column (largest groups first, capped so the plot stays readable).
 */
export function boxplotStats(
  rows: Row[],
  y: string,
  by: string | null,
  maxGroups = 12,
): BoxStats[] {
  const groups = new Map<string, number[]>();
  for (const row of rows) {
    const v = toNumber(row[y]);
    if (v === null) continue;
    const key = by ? blankLabel(row[by]) : "All rows";
    const list = groups.get(key) ?? [];
    list.push(v);
    groups.set(key, list);
  }
  return [...groups.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, maxGroups)
    .map(([category, values]) => {
      values.sort((a, b) => a - b);
      const q1 = quantile(values, 0.25);
      const median = quantile(values, 0.5);
      const q3 = quantile(values, 0.75);
      const iqr = q3 - q1;
      const loFence = q1 - 1.5 * iqr;
      const hiFence = q3 + 1.5 * iqr;
      const inside = values.filter((v) => v >= loFence && v <= hiFence);
      const lo = inside.length ? inside[0] : values[0];
      const hi = inside.length ? inside[inside.length - 1] : values[values.length - 1];
      return {
        category,
        lo,
        q1,
        median,
        q3,
        hi,
        count: values.length,
        outliers: values.length - inside.length,
      };
    });
}

// -- Smart column defaults ----------------------------------------------------
// When the user switches chart type, these pick columns that actually fit the
// chart's roles (measure, category, time axis) instead of "first alphabetical".

export interface ColumnMeta {
  columns: string[];
  /** Numeric, excluding datetime. */
  numeric: string[];
  /** Everything that is neither numeric nor datetime. */
  categorical: string[];
  datetime: string[];
  cardinality: Map<string, number>;
}

export function buildColumnMeta(rows: Row[], columns: string[]): ColumnMeta {
  const datetime = datetimeColumns(rows, columns);
  const dtSet = new Set(datetime);
  const numeric = numericColumns(rows, columns).filter((c) => !dtSet.has(c));
  const numSet = new Set(numeric);
  const categorical = columns.filter((c) => !dtSet.has(c) && !numSet.has(c));
  return { columns, numeric, categorical, datetime, cardinality: columnCardinalities(rows, columns) };
}

export interface ChartDefaults {
  column?: string;
  x?: string;
  y?: string;
  group?: string;
  aggregate?: Aggregate;
}

/** Identifier-ish columns make poor measures/categories — deprioritize them. */
function looksLikeId(name: string): boolean {
  return /(^|[_\s.-])(id|uuid|guid|key)$/i.test(name) || /^(id|uuid|guid|index|row_?num(ber)?)$/i.test(name);
}

/**
 * Best numeric column to aggregate/plot: numeric, not an id, actually varying
 * (a constant column charts as one giant block), not excluded.
 */
function bestMeasure(meta: ColumnMeta, exclude: string[] = []): string {
  const card = (c: string) => meta.cardinality.get(c) ?? 0;
  const pool = meta.numeric.filter((c) => !exclude.includes(c));
  return (
    pool.find((c) => !looksLikeId(c) && card(c) >= 2) ??
    pool.find((c) => !looksLikeId(c)) ??
    pool[0] ??
    meta.columns.find((c) => !exclude.includes(c)) ??
    ""
  );
}

/**
 * Best category column: prefers non-id text columns whose distinct count fits
 * the chart (most informative within [2, maxCard]); falls back to the lowest
 * cardinality otherwise.
 */
function bestCategory(meta: ColumnMeta, maxCard: number, exclude: string[] = []): string {
  const card = (c: string) => meta.cardinality.get(c) ?? 0;
  const pool = meta.categorical.filter((c) => !exclude.includes(c));
  const preferred = pool.filter((c) => !looksLikeId(c));
  for (const candidates of [preferred, pool]) {
    const inRange = candidates.filter((c) => card(c) >= 2 && card(c) <= maxCard);
    if (inRange.length) return inRange.reduce((a, b) => (card(b) > card(a) ? b : a));
  }
  // Nothing fits: the least-cardinal categorical still charts best after top-N capping.
  if (pool.length) return pool.reduce((a, b) => (card(b) < card(a) ? b : a));
  return meta.datetime.find((c) => !exclude.includes(c)) ?? meta.columns.find((c) => !exclude.includes(c)) ?? "";
}

/** Best small-cardinality column for grouping/stacking (2–8 distinct values). */
function bestGroup(meta: ColumnMeta, exclude: string[] = []): string {
  const card = (c: string) => meta.cardinality.get(c) ?? 0;
  const pool = meta.categorical.filter((c) => !exclude.includes(c) && card(c) >= 2);
  if (pool.length === 0) return "";
  const small = pool.filter((c) => card(c) <= 8);
  const candidates = small.length ? small : pool;
  return candidates.reduce((a, b) => (card(b) < card(a) ? b : a));
}

/** Best time-ish x axis: a datetime column, else the most continuous numeric. */
function bestTimeAxis(meta: ColumnMeta): string {
  if (meta.datetime.length) return meta.datetime[0];
  const card = (c: string) => meta.cardinality.get(c) ?? 0;
  const pool = meta.numeric.filter((c) => !looksLikeId(c));
  if (pool.length) return pool.reduce((a, b) => (card(b) > card(a) ? b : a));
  return meta.columns[0] ?? "";
}

/** Two distinct continuous numerics for a scatter plot. */
function bestScatterPair(meta: ColumnMeta): [string, string] {
  const card = (c: string) => meta.cardinality.get(c) ?? 0;
  const ranked = [
    ...meta.numeric.filter((c) => !looksLikeId(c)).sort((a, b) => card(b) - card(a)),
    ...meta.numeric.filter((c) => looksLikeId(c)),
  ];
  const x = ranked[0] ?? meta.columns[0] ?? "";
  const y = ranked.find((c) => c !== x) ?? meta.columns.find((c) => c !== x) ?? "";
  return [x, y];
}

/** Columns that fit each chart type's roles — applied when the type changes. */
export function chartDefaults(type: string, meta: ColumnMeta): ChartDefaults {
  // With no numeric column to aggregate, counting rows is the only honest rollup.
  const aggregate: Aggregate | undefined = meta.numeric.length === 0 ? "count" : undefined;
  switch (type) {
    case "histogramChart":
      return { column: bestMeasure(meta) };
    case "boxPlot": {
      const y = bestMeasure(meta);
      return { y, group: bestGroup(meta, [y]) };
    }
    case "valueCounts":
      return { column: bestCategory(meta, 50) };
    case "barChart":
    case "horizontalBarChart": {
      const x = bestCategory(meta, 30);
      return { x, y: bestMeasure(meta, [x]), aggregate };
    }
    case "pieChart": {
      const x = bestCategory(meta, 12);
      return { x, y: bestMeasure(meta, [x]), aggregate };
    }
    case "stackedBarChart": {
      const x = bestCategory(meta, 30);
      const group = bestGroup(meta, [x]);
      return { x, group, y: bestMeasure(meta, [x, group]), aggregate };
    }
    case "lineChart":
    case "areaChart": {
      const x = bestTimeAxis(meta);
      return { x, y: bestMeasure(meta, [x]) };
    }
    case "scatterChart": {
      const [x, y] = bestScatterPair(meta);
      return { x, y };
    }
    default:
      return {};
  }
}

/** Linear-interpolation quantile (R type 7) over a pre-sorted array. */
export function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0;
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sorted[base + 1];
  return next === undefined ? sorted[base] : sorted[base] + rest * (next - sorted[base]);
}

function aggregateValues(values: number[], aggregate: Aggregate): number {
  if (aggregate === "count") return values.length;
  if (values.length === 0) return 0;
  switch (aggregate) {
    case "sum":
      return values.reduce((s, v) => s + v, 0);
    case "mean":
      return values.reduce((s, v) => s + v, 0) / values.length;
    case "min":
      return Math.min(...values);
    case "max":
      return Math.max(...values);
    default:
      return 0;
  }
}

export interface StackedBarDatum {
  category: string;
  [group: string]: string | number;
}

/**
 * Pivot rows into stacked-bar format: one record per x-category with one
 * numeric property per group value, capped at the 8 top groups by total Y
 * magnitude so dense charts stay readable.
 */
export function stackedBarData(
  rows: Row[],
  x: string,
  y: string,
  group: string,
  aggregate: Aggregate,
): { data: StackedBarDatum[]; groups: string[] } {
  // Pick top-8 groups by total absolute Y so the legend doesn't explode.
  const groupTotals = new Map<string, number>();
  for (const row of rows) {
    const gKey = blankLabel(row[group]);
    groupTotals.set(gKey, (groupTotals.get(gKey) ?? 0) + Math.abs(toNumber(row[y]) ?? 0));
  }
  const topGroups = [...groupTotals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k]) => k);
  const topGroupSet = new Set(topGroups);

  const nested = new Map<string, Map<string, { values: number[]; rows: number }>>();
  for (const row of rows) {
    const xKey = blankLabel(row[x]);
    const gKey = blankLabel(row[group]);
    if (!topGroupSet.has(gKey)) continue;
    const v = toNumber(row[y]);
    if (!nested.has(xKey)) nested.set(xKey, new Map());
    const inner = nested.get(xKey)!;
    const cell = inner.get(gKey) ?? { values: [], rows: 0 };
    cell.rows += 1;
    if (v !== null) cell.values.push(v);
    inner.set(gKey, cell);
  }

  const data: StackedBarDatum[] = [...nested.entries()].map(([category, groups]) => {
    const datum: StackedBarDatum = { category };
    for (const g of topGroups) {
      const cell = groups.get(g);
      datum[g] =
        aggregate === "count"
          ? (cell?.rows ?? 0)
          : aggregateValues(cell?.values ?? [], aggregate);
    }
    return datum;
  });

  return { data, groups: topGroups };
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

function i_equals(a: number[], b: number[]): boolean {
  return a.length === 1 && b.length === 1 && a[0] === b[0];
}

function format(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}
