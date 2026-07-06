import { describe, expect, it } from "vitest";
import {
  buildRunValues,
  coerceDefault,
  defaultText,
  isRequired,
  referencedParameters,
  riskyParameterRefs,
  specToRow,
  validateRows,
  type ParamRow,
} from "@/lib/parameters";
import type { ParameterSpec } from "@/lib/types";

const row = (over: Partial<ParamRow> = {}): ParamRow => ({
  name: "p",
  type: "string",
  defaultText: "",
  description: "",
  ...over,
});

describe("coerceDefault", () => {
  it("treats empty text as no default (required)", () => {
    expect(coerceDefault("string", "")).toEqual({ ok: true, value: undefined });
    expect(coerceDefault("integer", "   ")).toEqual({ ok: true, value: undefined });
  });

  it("keeps strings verbatim (including whitespace)", () => {
    expect(coerceDefault("string", " a b ")).toEqual({ ok: true, value: " a b " });
  });

  it("parses integers and rejects non-integers", () => {
    expect(coerceDefault("integer", "42")).toEqual({ ok: true, value: 42 });
    expect(coerceDefault("integer", "-7")).toEqual({ ok: true, value: -7 });
    expect(coerceDefault("integer", "1.5")).toEqual({ ok: false });
    expect(coerceDefault("integer", "abc")).toEqual({ ok: false });
  });

  it("rejects integers past JS safe-integer precision", () => {
    // Would silently round to 1e20 and send a different number to the backend.
    expect(coerceDefault("integer", "99999999999999999999")).toEqual({ ok: false });
    expect(coerceDefault("integer", String(Number.MAX_SAFE_INTEGER))).toEqual({
      ok: true,
      value: Number.MAX_SAFE_INTEGER,
    });
  });

  it("parses numbers and rejects garbage", () => {
    expect(coerceDefault("number", "2.5")).toEqual({ ok: true, value: 2.5 });
    expect(coerceDefault("number", "nope")).toEqual({ ok: false });
  });

  it("parses booleans from common tokens", () => {
    expect(coerceDefault("boolean", "true")).toEqual({ ok: true, value: true });
    expect(coerceDefault("boolean", "False")).toEqual({ ok: true, value: false });
    expect(coerceDefault("boolean", "maybe")).toEqual({ ok: false });
  });
});

describe("validateRows", () => {
  it("produces typed specs for valid rows", () => {
    const { errors, specs } = validateRows([
      row({ name: "keep", type: "integer", defaultText: "2", description: "rows" }),
      row({ name: "flag", type: "boolean", defaultText: "true" }),
    ]);
    expect(errors.size).toBe(0);
    expect(specs).toEqual([
      { name: "keep", type: "integer", default: 2, description: "rows" },
      { name: "flag", type: "boolean", default: true },
    ]);
  });

  it("omits default when none is given (required parameter)", () => {
    const { specs } = validateRows([row({ name: "x", type: "string" })]);
    expect(specs).toEqual([{ name: "x", type: "string" }]);
  });

  it("flags blank, malformed and duplicate names", () => {
    const { errors, specs } = validateRows([
      row({ name: "" }),
      row({ name: "1bad" }),
      row({ name: "ok" }),
      row({ name: "ok" }),
    ]);
    expect(specs).toBeNull();
    expect(errors.get(0)).toMatch(/required/i);
    expect(errors.get(1)).toMatch(/letters/i);
    expect(errors.get(3)).toMatch(/duplicate/i);
  });

  it("flags an uncoercible default", () => {
    const { errors, specs } = validateRows([row({ name: "n", type: "integer", defaultText: "x" })]);
    expect(specs).toBeNull();
    expect(errors.get(0)).toMatch(/valid integer/i);
  });
});

describe("specToRow", () => {
  it("renders default as text and null as empty", () => {
    expect(specToRow({ name: "n", type: "integer", default: 5 })).toMatchObject({ defaultText: "5" });
    expect(specToRow({ name: "n", type: "string", default: null })).toMatchObject({ defaultText: "" });
    expect(specToRow({ name: "n", type: "string" })).toMatchObject({ defaultText: "" });
  });
});

describe("isRequired / defaultText", () => {
  it("treats absent or null default as required", () => {
    expect(isRequired({ name: "n", type: "string" })).toBe(true);
    expect(isRequired({ name: "n", type: "string", default: null })).toBe(true);
    expect(isRequired({ name: "n", type: "integer", default: 0 })).toBe(false);
  });

  it("renders defaultText, including falsy defaults", () => {
    expect(defaultText({ name: "n", type: "integer", default: 0 })).toBe("0");
    expect(defaultText({ name: "b", type: "boolean", default: false })).toBe("false");
    expect(defaultText({ name: "n", type: "string" })).toBe("");
  });
});

describe("buildRunValues", () => {
  const specs: ParameterSpec[] = [
    { name: "keep", type: "integer", default: 2 },
    { name: "label", type: "string" }, // required
  ];

  it("coerces supplied values and errors on missing required", () => {
    const { errors, values } = buildRunValues(specs, { keep: "5" });
    expect(values).toBeNull();
    expect(errors.get("label")).toMatch(/required/i);
  });

  it("omits blank optional fields so defaults apply", () => {
    const { values } = buildRunValues(specs, { keep: "", label: "x" });
    expect(values).toEqual({ label: "x" });
  });

  it("errors on an invalid typed override", () => {
    const { errors, values } = buildRunValues(specs, { keep: "abc", label: "x" });
    expect(values).toBeNull();
    expect(errors.get("keep")).toMatch(/valid integer/i);
  });

  it("returns an empty object when everything falls back to defaults", () => {
    const { values } = buildRunValues([{ name: "keep", type: "integer", default: 2 }], {});
    expect(values).toEqual({});
  });
});

describe("referencedParameters", () => {
  it("collects {{ name }} references across nested config", () => {
    const refs = referencedParameters({
      a: "{{ keep }}",
      b: ["data/{{ date }}.csv", 3, true],
      c: { d: "no refs", e: "{{ keep }} and {{ extra }}" },
    });
    expect([...refs].sort()).toEqual(["date", "extra", "keep"]);
  });

  it("returns empty for configs without references", () => {
    expect(referencedParameters({ a: "x", b: 1 }).size).toBe(0);
  });
});

describe("riskyParameterRefs", () => {
  it("flags a parameter referenced in a pythonTransform script", () => {
    const refs = riskyParameterRefs("pythonTransform", { script: "return df.head({{ n }})" });
    expect([...refs]).toEqual(["n"]);
  });

  it("flags a parameter referenced in an assertExpression/calculatedColumn expression", () => {
    expect([...riskyParameterRefs("assertExpression", { expression: "x > {{ threshold }}" })]).toEqual([
      "threshold",
    ]);
    expect([...riskyParameterRefs("calculatedColumn", { expression: "a * {{ factor }}" })]).toEqual([
      "factor",
    ]);
  });

  it("flags a parameter referenced in a filterExpression expression", () => {
    expect([...riskyParameterRefs("filterExpression", { expression: "age > {{ threshold }}" })]).toEqual([
      "threshold",
    ]);
  });

  it("flags a parameter referenced in a sqlInput query", () => {
    const refs = riskyParameterRefs("sqlInput", { query: "SELECT * FROM t WHERE city = '{{ city }}'" });
    expect([...refs]).toEqual(["city"]);
  });

  it("ignores references in ordinary (non-code) fields and unknown node types", () => {
    expect(riskyParameterRefs("csvOutput", { dataset_name: "{{ out }}" }).size).toBe(0);
    expect(riskyParameterRefs("filterRows", { value: "{{ threshold }}" }).size).toBe(0);
  });

  it("ignores fields on a risky node type other than the risky one", () => {
    expect(riskyParameterRefs("pythonTransform", { label: "{{ n }}" }).size).toBe(0);
  });
});
