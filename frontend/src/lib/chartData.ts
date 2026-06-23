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
  const groups = new Map<string, number[]>();
  for (const row of rows) {
    const key = String(row[x] ?? "");
    const v = toNumber(row[y]);
    const list = groups.get(key) ?? [];
    if (v !== null) list.push(v);
    groups.set(key, list);
  }
  return [...groups.entries()].map(([category, values]) => ({
    category,
    value: aggregateValues(values, aggregate),
  }));
}

/** Count how many rows fall into each distinct value of a column (frequency). */
export function valueCounts(rows: Row[], column: string): BarDatum[] {
  const groups = new Map<string, number>();
  for (const row of rows) {
    const cell = row[column];
    const key = cell === null || cell === undefined || cell === "" ? "(blank)" : String(cell);
    groups.set(key, (groups.get(key) ?? 0) + 1);
  }
  return [...groups.entries()].map(([category, value]) => ({ category, value }));
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

/** Map a correlation value in [-1, 1] to a blue↔red CSS colour. */
export function correlationColor(value: number): string {
  const v = clamp(value, -1, 1);
  // Positive → red, negative → blue, zero → near-white.
  if (v >= 0) {
    const t = v;
    const g = Math.round(255 * (1 - t));
    const b = Math.round(255 * (1 - t));
    return `rgb(255, ${g}, ${b})`;
  }
  const t = -v;
  const r = Math.round(255 * (1 - t));
  const g = Math.round(255 * (1 - t));
  return `rgb(${r}, ${g}, 255)`;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

function i_equals(a: number[], b: number[]): boolean {
  return a.length === 1 && b.length === 1 && a[0] === b[0];
}

function format(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}
