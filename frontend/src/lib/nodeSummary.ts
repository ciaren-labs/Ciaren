// One-line, human-readable summary of a node's configuration, shown under the
// node's label on the canvas. Its purpose is misconfiguration triage at a
// glance: a wrong subtitle is spotted without opening the sidebar, and a node
// whose key fields are still empty shows no subtitle at all (nodes whose
// defaults are already meaningful — limit 100 rows, CSV output — summarize
// those defaults). Pure — unit-tested directly.

import { getModelDef, TRAIN_NODE_TASKS } from "./mlModels";

const MAX_LEN = 46;

function clip(s: string): string {
  return s.length > MAX_LEN ? `${s.slice(0, MAX_LEN - 1)}…` : s;
}

function str(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

/** Numbers may arrive as strings from legacy/imported flows (the zod schemas
 *  coerce them at validation time), so coerce numeric strings here too. */
function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function strArr(v: unknown): string[] {
  return Array.isArray(v)
    ? v.filter((x): x is string => typeof x === "string" && x.trim() !== "")
    : [];
}

/** "a", "a, b", or "3 columns" — short enough to sit on a node card. */
function listOf(items: string[], noun = "column"): string {
  if (items.length <= 2) return items.join(", ");
  return `${items.length} ${noun}s`;
}

function recordSize(v: unknown): number {
  return v && typeof v === "object" && !Array.isArray(v) ? Object.keys(v).length : 0;
}

/** Extra context some summaries need that isn't in the node config itself. */
export interface NodeSummaryContext {
  /** Name of the dataset the node's dataset_id points at, when known. */
  datasetName?: string | null;
}

/**
 * A short subtitle describing `config` for a node of `type`, or null when
 * there is nothing meaningful configured yet (the card then shows nothing —
 * required-field enforcement is validation's job, not the subtitle's).
 */
export function getNodeSummary(
  type: string,
  config: Record<string, unknown>,
  ctx: NodeSummaryContext = {},
): string | null {
  const c = config;

  // Train / model-definition nodes: the chosen algorithm is the one fact that
  // matters on the card (matches the editor's long-standing behavior).
  if (type in TRAIN_NODE_TASKS) {
    const model = getModelDef(str(c.model_type));
    return model?.label ?? null;
  }

  switch (type) {
    // ----- Inputs -----
    case "fileInput":
    case "csvInput":
    case "excelInput":
    case "parquetInput":
    case "jsonInput":
    case "textInput": {
      const name = str(ctx.datasetName);
      if (!name) return null;
      const version = num(c.dataset_version);
      return clip(version != null ? `${name} · v${version}` : name);
    }
    case "sqlInput": {
      if (str(c.mode) === "query") return str(c.query) ? "custom query" : null;
      const table = str(c.table);
      if (!table) return null;
      const schema = str(c.schema);
      return clip(schema ? `${schema}.${table}` : table);
    }
    case "storageInput": {
      const path = str(c.path);
      return path ? clip(`${str(c.format).toUpperCase() || "?"} · ${path}`) : null;
    }

    // ----- Cleaning -----
    case "dropNulls": {
      const subset = strArr(c.subset);
      const all = str(c.how) === "all";
      if (!subset.length) return all ? "rows fully null" : "any null value";
      return clip(`in ${listOf(subset)}${all ? " (all null)" : ""}`);
    }
    case "fillNulls": {
      const strategy = str(c.strategy) || "constant";
      if (strategy === "constant") {
        const value = str(c.value);
        return value ? clip(`constant "${value}"`) : null;
      }
      return strategy;
    }
    case "removeDuplicates": {
      const subset = strArr(c.subset);
      return subset.length ? clip(`by ${listOf(subset)}`) : "whole rows";
    }
    case "filterRows": {
      const column = str(c.column);
      const op = str(c.operator);
      if (!column || !op) return null;
      if (op === "isnull") return clip(`${column} is null`);
      if (op === "notnull") return clip(`${column} is not null`);
      const value = str(c.value) || String(num(c.value) ?? "");
      if (op === "between") {
        const upper = str(c.value2) || String(num(c.value2) ?? "");
        return clip(`${column} between ${value} … ${upper}`.trim());
      }
      return clip(`${column} ${op} ${value}`.trim());
    }
    case "filterExpression":
    case "assertExpression": {
      const expr = str(c.expression);
      return expr ? clip(expr) : null;
    }
    case "sortRows": {
      const columns = strArr(c.columns);
      if (!columns.length) return null;
      return clip(`${listOf(columns)} ${c.ascending === false ? "↓" : "↑"}`);
    }
    case "castDtypes": {
      const n = recordSize(c.casts);
      return n ? `${n} cast${n > 1 ? "s" : ""}` : null;
    }
    case "limitRows": {
      const n = num(c.n);
      if (n == null) return null;
      const offset = num(c.offset);
      return offset ? `${n} rows from ${offset}` : `first ${n} rows`;
    }
    case "sampleRows": {
      // Fraction mode sets `frac` and clears `n`.
      const frac = num(c.frac);
      if (frac != null) return `${Math.round(frac * 100)}% sample`;
      const n = num(c.n);
      return n != null ? `${n} rows` : null;
    }

    // ----- Columns -----
    case "dropColumns":
    case "selectColumns":
    case "parseDates":
    case "roundNumbers": {
      const columns = strArr(c.columns);
      return columns.length ? clip(listOf(columns)) : null;
    }
    case "renameColumns": {
      const n = recordSize(c.mapping);
      return n ? `${n} renamed` : null;
    }
    case "combineColumns":
    case "coalesceColumns": {
      const columns = strArr(c.columns);
      const target = str(c.new_column);
      if (!columns.length || !target) return null;
      return clip(`${listOf(columns)} → ${target}`);
    }
    case "replaceValues": {
      const column = str(c.column);
      return column ? clip(`${column}: "${str(c.to_replace)}" → "${str(c.value)}"`) : null;
    }
    case "stringTransform": {
      const column = str(c.column);
      return column ? clip(`${str(c.operation) || "lower"}(${column})`) : null;
    }
    case "calculatedColumn": {
      const name = str(c.column_name);
      const expr = str(c.expression);
      if (!name && !expr) return null;
      return clip(name && expr ? `${name} = ${expr}` : name || expr);
    }
    case "mapValues": {
      const column = str(c.column);
      const n = recordSize(c.mapping);
      if (!column) return null;
      return clip(n ? `${column} · ${n} mapping${n > 1 ? "s" : ""}` : column);
    }
    case "splitColumn": {
      const column = str(c.column);
      if (!column) return null;
      return clip(
        str(c.mode) === "regex" ? `${column} by regex` : `${column} by "${str(c.delimiter)}"`,
      );
    }

    // ----- Reshape -----
    case "join": {
      const how = str(c.how) || "inner";
      const on = strArr(c.on);
      const onStr = on.length ? listOf(on, "key") : str(c.on);
      if (onStr) return clip(`${how} on ${onStr}`);
      // Split-key mode: different column names on each side.
      const left = strArr(c.left_on);
      const right = strArr(c.right_on);
      if (left.length && right.length) {
        return clip(`${how} on ${listOf(left, "key")} = ${listOf(right, "key")}`);
      }
      return null;
    }
    case "groupByAggregate": {
      const by = strArr(c.group_by);
      const nAggs = recordSize(c.aggregations);
      if (!by.length && !nAggs) return null;
      const parts = [];
      if (by.length) parts.push(`by ${listOf(by)}`);
      if (nAggs) parts.push(`${nAggs} agg${nAggs > 1 ? "s" : ""}`);
      return clip(parts.join(" · "));
    }
    case "unpivot": {
      const values = strArr(c.value_vars);
      return values.length ? clip(`${listOf(values)} → rows`) : null;
    }
    case "pivot": {
      const columns = str(c.columns);
      const values = str(c.values);
      if (!columns || !values) return null;
      return clip(`${columns} × ${str(c.aggfunc) || "sum"}(${values})`);
    }
    case "explodeRows": {
      const column = str(c.column);
      return column ? clip(`${column} by "${str(c.delimiter)}"`) : null;
    }

    // ----- Analytics -----
    case "removeOutliers": {
      const columns = strArr(c.columns);
      if (!columns.length) return null;
      return clip(`${str(c.method) || "iqr"} · ${str(c.action) || "drop"} · ${listOf(columns)}`);
    }
    case "binColumn": {
      const column = str(c.column);
      const bins = num(c.bins);
      return column ? clip(`${column} → ${bins ?? "?"} bins`) : null;
    }
    case "extractDateParts": {
      const column = str(c.column);
      const parts = strArr(c.parts);
      if (!column) return null;
      return clip(parts.length ? `${column}: ${listOf(parts, "part")}` : column);
    }
    case "windowFunction": {
      const fn = str(c.function);
      if (!fn) return null;
      const target = str(c.target);
      return clip(target ? `${fn}(${target})` : fn);
    }
    case "conditionalColumn": {
      const name = str(c.new_column);
      const rules = Array.isArray(c.rules) ? c.rules.length : 0;
      if (!name) return null;
      return clip(`→ ${name} (${rules} rule${rules === 1 ? "" : "s"})`);
    }
    case "rollingAggregate": {
      const target = str(c.target);
      if (!target) return null;
      return clip(`${str(c.function) || "mean"}(${target}) over ${num(c.window) ?? "?"}`);
    }
    case "rowDifference": {
      const target = str(c.target);
      return target ? clip(`${str(c.method) || "diff"}(${target})`) : null;
    }
    case "dateDifference": {
      const start = str(c.start_column);
      const end = str(c.end_column);
      if (!start || !end) return null;
      return clip(`${end} − ${start} (${str(c.unit) || "days"})`);
    }
    case "pythonTransform":
      return "custom script";

    // ----- Data Quality -----
    case "assertNotNull":
    case "assertUnique": {
      const columns = strArr(c.columns);
      return columns.length ? clip(listOf(columns)) : null;
    }
    case "assertValueRange": {
      const column = str(c.column);
      if (!column) return null;
      const min = num(c.min);
      const max = num(c.max);
      if (min == null && max == null) return clip(column);
      return clip(`${column} in [${min ?? "−∞"}, ${max ?? "∞"}]`);
    }
    case "assertRowCount": {
      const min = num(c.min_rows);
      const max = num(c.max_rows);
      if (min == null && max == null) return null;
      if (min != null && max != null) return `${min}–${max} rows`;
      return min != null ? `≥ ${min} rows` : `≤ ${max} rows`;
    }
    case "assertValuesInSet": {
      const column = str(c.column);
      const allowed = strArr(c.allowed);
      if (!column) return null;
      return clip(`${column}: ${allowed.length} allowed`);
    }

    // ----- Machine Learning -----
    case "trainTestSplit": {
      const testSize = num(c.test_size);
      return testSize != null ? `${Math.round(testSize * 100)}% test` : null;
    }
    case "scaleFeatures":
    case "encodeCategories":
    case "selectFeatures": {
      const method = str(c.method);
      return method || null;
    }
    case "reduceDimensions": {
      const n = num(c.n_components);
      return clip(`${str(c.method) || "pca"} → ${n ?? "?"}`);
    }
    case "mlPredict": {
      const uri = str(c.model_uri);
      if (uri) return clip(uri);
      const out = str(c.output_column);
      return out ? clip(`→ ${out}`) : null;
    }
    case "mlEvaluate": {
      const task = str(c.task_type);
      return task || null;
    }
    case "featureImportance": {
      const topN = num(c.top_n);
      return topN != null ? `top ${topN}` : null;
    }
    case "mlCrossValidate": {
      const strategy = str(c.cv_strategy);
      const splits = num(c.n_splits);
      if (!strategy) return null;
      return splits != null ? `${strategy} × ${splits}` : strategy;
    }

    // ----- Outputs -----
    case "fileOutput": {
      const format = str(c.format).toUpperCase() || "CSV";
      const name = str(c.dataset_name);
      return clip(name ? `${format} → ${name}` : format);
    }
    case "csvOutput":
    case "excelOutput":
    case "parquetOutput": {
      const path = str(c.path);
      return path ? clip(path) : null;
    }
    case "sqlOutput": {
      const table = str(c.table);
      if (!table) return null;
      const schema = str(c.schema);
      return clip(`→ ${schema ? `${schema}.${table}` : table}`);
    }
    case "storageOutput": {
      const path = str(c.path);
      return path ? clip(`${str(c.format).toUpperCase() || "?"} → ${path}`) : null;
    }

    default:
      return null;
  }
}
