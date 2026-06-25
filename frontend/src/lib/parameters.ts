// Client-side helpers for authoring flow parameters. The backend re-validates
// everything (app/engine/parameters.py); this mirrors the rules for fast editor
// feedback and to coerce default values to their declared type before saving.

import type { ParameterSpec, ParameterType, ParameterValues } from "@/lib/types";

const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** An editable parameter row: `default` is held as raw text while editing. */
export interface ParamRow {
  name: string;
  type: ParameterType;
  defaultText: string;
  description: string;
}

/** Turn a persisted spec into an editable row (default rendered as text). */
export function specToRow(spec: ParameterSpec): ParamRow {
  return {
    name: spec.name,
    type: spec.type,
    defaultText: spec.default === undefined || spec.default === null ? "" : String(spec.default),
    description: spec.description ?? "",
  };
}

export function emptyRow(): ParamRow {
  return { name: "", type: "string", defaultText: "", description: "" };
}

/** Coerce a default's raw text to its declared type. Empty text → `undefined`
 *  (the parameter becomes required). Returns `{ ok: false }` on a bad value. */
export function coerceDefault(
  type: ParameterType,
  text: string,
): { ok: true; value: unknown } | { ok: false } {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: undefined };
  switch (type) {
    case "string":
      return { ok: true, value: text };
    case "integer": {
      if (!/^[+-]?\d+$/.test(trimmed)) return { ok: false };
      const n = Number(trimmed);
      // Reject values past 2^53 — JS loses integer precision, so the number sent
      // to the backend would silently differ from what was typed.
      if (!Number.isSafeInteger(n)) return { ok: false };
      return { ok: true, value: n };
    }
    case "number": {
      const n = Number(trimmed);
      if (!Number.isFinite(n)) return { ok: false };
      return { ok: true, value: n };
    }
    case "boolean": {
      const t = trimmed.toLowerCase();
      if (["true", "1", "yes", "on"].includes(t)) return { ok: true, value: true };
      if (["false", "0", "no", "off"].includes(t)) return { ok: true, value: false };
      return { ok: false };
    }
  }
}

export interface ParamValidation {
  /** Row-index → message for the first problem on that row. */
  errors: Map<number, string>;
  /** The coerced specs, or null when any row is invalid. */
  specs: ParameterSpec[] | null;
}

/** Validate a set of editable rows and, when all valid, produce the specs to save. */
export function validateRows(rows: ParamRow[]): ParamValidation {
  const errors = new Map<number, string>();
  const seen = new Set<string>();
  const specs: ParameterSpec[] = [];

  rows.forEach((row, i) => {
    const name = row.name.trim();
    if (!name) {
      errors.set(i, "Name is required.");
      return;
    }
    if (!NAME_RE.test(name)) {
      errors.set(i, "Use letters, digits, underscores; must not start with a digit.");
      return;
    }
    if (seen.has(name)) {
      errors.set(i, `Duplicate parameter name "${name}".`);
      return;
    }
    seen.add(name);

    const coerced = coerceDefault(row.type, row.defaultText);
    if (!coerced.ok) {
      errors.set(i, `Default is not a valid ${row.type}.`);
      return;
    }
    const spec: ParameterSpec = { name, type: row.type };
    if (coerced.value !== undefined) spec.default = coerced.value;
    const desc = row.description.trim();
    if (desc) spec.description = desc;
    specs.push(spec);
  });

  return { errors, specs: errors.size === 0 ? specs : null };
}

/** A parameter with neither a default nor a (later) override must be supplied. */
export function isRequired(spec: ParameterSpec): boolean {
  return spec.default === undefined || spec.default === null;
}

/** The default rendered as input text (empty when the parameter is required). */
export function defaultText(spec: ParameterSpec): string {
  return isRequired(spec) ? "" : String(spec.default);
}

export interface RunValues {
  /** Parameter name → message for the first problem with its value. */
  errors: Map<string, string>;
  /** Coerced override values (only fields the user supplied), or null on error.
   *  A field left blank falls back to its default and is omitted here. */
  values: ParameterValues | null;
}

/** Validate run/schedule override text per spec and coerce to typed values. */
export function buildRunValues(
  specs: ParameterSpec[],
  texts: Record<string, string>,
): RunValues {
  const errors = new Map<string, string>();
  const values: ParameterValues = {};

  for (const spec of specs) {
    const raw = texts[spec.name] ?? "";
    if (raw.trim() === "") {
      if (isRequired(spec)) errors.set(spec.name, "This parameter is required.");
      continue; // blank + has default → use the default (omit the override)
    }
    const coerced = coerceDefault(spec.type, raw);
    if (!coerced.ok) {
      errors.set(spec.name, `Enter a valid ${spec.type}.`);
      continue;
    }
    values[spec.name] = coerced.value;
  }

  return { errors, values: errors.size === 0 ? values : null };
}

/** Find the `{{ name }}` references used anywhere in a node-config tree. */
export function referencedParameters(value: unknown): Set<string> {
  const found = new Set<string>();
  const walk = (v: unknown) => {
    if (typeof v === "string") {
      for (const m of v.matchAll(/\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g)) found.add(m[1]);
    } else if (Array.isArray(v)) {
      v.forEach(walk);
    } else if (v && typeof v === "object") {
      Object.values(v).forEach(walk);
    }
  };
  walk(value);
  return found;
}
